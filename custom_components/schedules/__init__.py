"""The schedule integration."""

import logging

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import WEEKDAYS
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity_registry import (
    async_get_registry as get_entity_registry,
)

from . import const
from .store import async_get_registry
from .util import validate_condition_str, validate_time_str, validate_weekdays

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1
STORAGE_KEY = f"{const.DOMAIN}_storage"
SAVE_DELAY = 10


async def async_setup(hass: HomeAssistant, config: dict):
    """Initialize basic config."""
    hass.data[const.DATA_DOMAIN] = {
        const.DATA_WORKDAY_SENSOR: None,
        const.DATA_SCHEDULES: {},
    }
    return True


async def async_options_updated(hass: HomeAssistant, entry: ConfigEntry):
    """Handle options update."""
    workday_sensor = entry.options.get(
        "workday_sensor", entry.data.get("workday_sensor")
    )
    hass.data[const.DATA_DOMAIN][const.DATA_WORKDAY_SENSOR] = workday_sensor
    for sched in hass.data[const.DATA_DOMAIN][const.DATA_SCHEDULES].values():
        await sched.async_update_sensor()


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up from a config entry."""

    await async_options_updated(hass, entry)
    entry.add_update_listener(async_options_updated)

    # Load platforms
    for component in ["binary_sensor", "sensor"]:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    # get the stored schedules from disk
    store = await async_get_registry(hass)

    @callback
    def binary_sensor_platform_loaded():
        """Handle callback when Binary Sensor platform is loaded."""
        for item in store.schedules.values():
            async_dispatcher_send(hass, "new_schedule_registered", item.schedule_id)

    async_dispatcher_connect(
        hass, "schedule_binary_sensor_platform_loaded", binary_sensor_platform_loaded
    )

    # Register Services
    await register_services(hass)

    return True


async def register_services(hass: HomeAssistant):
    """Register all our services."""

    async def add_schedule(service):
        """Add a new schedule."""
        store = await async_get_registry(hass)
        new_sched = store.async_create(
            schedule_id=service.data[const.ATTR_SCHEDULE_ID],
            after=service.data[const.ATTR_TIME_AFTER],
            before=service.data[const.ATTR_TIME_BEFORE],
            weekdays=service.data[const.ATTR_WEEKDAYS],
            condition=service.data[const.ATTR_CONDITION],
        )
        async_dispatcher_send(hass, "new_schedule_registered", new_sched.schedule_id)

    async def delete_schedule(service):
        """Delete an existing schedule."""
        store = await async_get_registry(hass)
        schedule_id = service.data[const.ATTR_SCHEDULE_ID]
        if store.async_delete(schedule_id):
            # remove entity from hass
            entity_id = hass.data[const.DATA_DOMAIN][const.DATA_SCHEDULES][
                schedule_id
            ].entity_id
            await hass.data[const.DATA_DOMAIN][const.DATA_SCHEDULES][
                schedule_id
            ].async_remove()
            hass.data[const.DATA_DOMAIN][const.DATA_SCHEDULES].pop(schedule_id, None)
            # remove entity from entity registry
            entity_registry = await get_entity_registry(hass)
            entity_registry.async_remove(entity_id)
            async_dispatcher_send(hass, "schedule_updated", schedule_id)
            _LOGGER.warning("Schedule deleted: %s", schedule_id)

    async def update_schedule(service):
        """Update an existing schedule."""
        store = await async_get_registry(hass)
        schedule_id = service.data[const.ATTR_SCHEDULE_ID]
        store.async_update(schedule_id, service.data)
        await hass.data[const.DATA_DOMAIN][const.DATA_SCHEDULES][
            schedule_id
        ].async_initialize_sensor()

    hass.services.async_register(
        const.DOMAIN,
        const.SERVICE_ADD_SCHEDULE,
        add_schedule,
        schema=vol.Schema(
            {
                vol.Required(const.ATTR_SCHEDULE_ID): str,
                vol.Required(const.ATTR_TIME_BEFORE): validate_time_str,
                vol.Required(const.ATTR_TIME_AFTER): validate_time_str,
                vol.Optional(const.ATTR_WEEKDAYS, default=WEEKDAYS): validate_weekdays,
                vol.Optional(
                    const.ATTR_CONDITION, default=None
                ): validate_condition_str,
            }
        ),
    )
    hass.services.async_register(
        const.DOMAIN,
        const.SERVICE_DELETE_SCHEDULE,
        delete_schedule,
        schema=vol.Schema({vol.Required(const.ATTR_SCHEDULE_ID): str}),
    )
    hass.services.async_register(
        const.DOMAIN,
        const.SERVICE_UPDATE_SCHEDULE,
        update_schedule,
        schema=vol.Schema(
            {
                vol.Required(const.ATTR_SCHEDULE_ID): str,
                vol.Optional(const.ATTR_TIME_BEFORE): validate_time_str,
                vol.Optional(const.ATTR_TIME_AFTER): validate_time_str,
                vol.Optional(const.ATTR_WEEKDAYS): validate_weekdays,
                vol.Optional(const.ATTR_CONDITION): validate_condition_str,
            }
        ),
    )
