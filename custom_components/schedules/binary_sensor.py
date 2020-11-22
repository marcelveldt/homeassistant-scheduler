"""Representation of a schedule (presented as hass binary sensor)."""

import logging

import homeassistant.util.dt as dt_util
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.const import SUN_EVENT_SUNRISE, SUN_EVENT_SUNSET, WEEKDAYS
from homeassistant.core import callback
from homeassistant.helpers.condition import async_template as templ_match
from homeassistant.helpers.condition import time as time_match
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.event import (
    async_track_state_change,
    async_track_sunrise,
    async_track_sunset,
    async_track_template,
    async_track_time_change,
)

from . import const
from .store import async_get_registry
from .util import parse_sun_event, parse_template, parse_time

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up binary_sensor from config entry."""

    @callback
    def async_add_schedule_sensor(schedule_id):
        """Add each schedule as Binary Sensor."""
        sched_sensor = ScheduleSensor(hass, schedule_id)
        async_add_entities([sched_sensor])
        hass.data[const.DATA_DOMAIN][const.DATA_SCHEDULES][schedule_id] = sched_sensor

    async_dispatcher_connect(hass, "new_schedule_registered", async_add_schedule_sensor)
    async_dispatcher_send(hass, "schedule_binary_sensor_platform_loaded")


class ScheduleSensor(BinarySensorEntity):
    """Representation of single schedule, optionally exposed as binary sensor."""

    @property
    def is_on(self):
        """Return if the sensor is on or off."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return the device specific state attributes."""
        return {
            const.ATTR_TIME_BEFORE: self.before,
            const.ATTR_TIME_AFTER: self.after,
            const.ATTR_WEEKDAYS: self.weekdays,
            const.ATTR_SCHEDULE_ID: self.schedule_id,
            const.ATTR_CONDITION: self.condition,
        }

    @property
    def name(self):
        """Return the (default) name of the schedule."""
        return f"Schedule {self.schedule_id}"

    @property
    def before(self):
        """Return the time_before of the schedule."""
        return self._schedule_entry.before if self._schedule_entry else None

    @property
    def after(self):
        """Return the time_after of the schedule."""
        return self._schedule_entry.after if self._schedule_entry else None

    @property
    def weekdays(self):
        """Return the weekdays of the schedule."""
        return self._schedule_entry.weekdays if self._schedule_entry else []

    @property
    def unique_id(self):
        """Return the unique_id of the schedule."""
        return self.schedule_id

    @property
    def condition(self):
        """Return the condition of the schedule."""
        return self._schedule_entry.condition if self._schedule_entry else None

    @property
    def should_poll(self):
        """Return a bool if this entity should be actively polled for status."""
        return False

    def __init__(self, hass, schedule_id):
        """Initialize entity."""
        self.hass = hass
        self.schedule_id = schedule_id
        self._state_listeners = []
        self._schedule_entry = None
        self._condition_template = None
        self._state = False

    async def async_added_to_hass(self):
        """Call when entity is added."""
        self.hass.loop.create_task(self.async_initialize_sensor())

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        self.__deregister_listeners()

    async def async_initialize_sensor(self):
        """Run all tasks to initialize the schedule sensor."""
        store = await async_get_registry(self.hass)
        self._schedule_entry = store.async_get(self.schedule_id)
        self.__deregister_listeners()
        self.__register_condition_template()
        self.__register_listeners()
        await self.async_update_state()
        _LOGGER.debug("Schedule initialized: %s", self.name)

    @callback
    def __deregister_listeners(self):
        """Make sure that existing listeners are deregistered."""
        for remove_listener in self._state_listeners:
            remove_listener()
        self._state_listeners = []

    @callback
    def __register_condition_template(self):
        """Unpack templated condition."""
        if self._schedule_entry.condition:
            self._condition_template = parse_template(self._schedule_entry.condition)
            self._condition_template.hass = self.hass
        else:
            self._condition_template = None

    @callback
    def __register_listeners(self):
        """Register listeners that track state changes."""

        @callback
        def event_fired(*args, **kwargs):
            """Handle an event from HomeAssistant as trigger to update our sensor."""
            _LOGGER.debug("trigger: %s", args)
            self.hass.loop.create_task(self.async_update_state())

        # parse entities/time we need to track
        for time_str in [self._schedule_entry.after, self._schedule_entry.before]:
            if SUN_EVENT_SUNRISE in time_str or SUN_EVENT_SUNSET in time_str:
                # sunrise/sunset (with or without offset)
                sun_event, offset = parse_sun_event(self.hass, time_str)
                if sun_event == SUN_EVENT_SUNRISE:
                    self._state_listeners.append(
                        async_track_sunrise(self.hass, event_fired, offset)
                    )
                elif sun_event == SUN_EVENT_SUNSET:
                    self._state_listeners.append(
                        async_track_sunset(self.hass, event_fired, offset)
                    )
            else:
                # regular time
                time_val = parse_time(self.hass, time_str)
                self._state_listeners.append(
                    async_track_time_change(
                        self.hass,
                        event_fired,
                        time_val.hour,
                        time_val.minute,
                        time_val.second,
                    )
                )
        # append listener(s) for templated condition
        if self._condition_template:
            self._state_listeners.append(
                async_track_template(self.hass, self._condition_template, event_fired)
            )
        # append listener for workday sensor
        workday_sensor = self.hass.data[const.DATA_DOMAIN][const.DATA_WORKDAY_SENSOR]
        if workday_sensor:
            self._state_listeners.append(
                async_track_state_change(self.hass, workday_sensor, event_fired)
            )

    async def async_update_state(self):
        """Calculate current state of the sensor."""
        if self.before is None or self.after is None:
            self._state = False
        # weekday/workday match
        now = dt_util.now()
        day_matches = WEEKDAYS[now.weekday()] in self.weekdays
        if not day_matches:
            # weekday OR workday must match
            workday_sensor = self.hass.data[const.DATA_DOMAIN][
                const.DATA_WORKDAY_SENSOR
            ]
            if workday_sensor and "workday" in self.weekdays:
                if self.hass.states.get(workday_sensor).state == "on":
                    day_matches = True
            elif workday_sensor and "not_workday" in self.weekdays:
                if self.hass.states.get(workday_sensor).state == "off":
                    day_matches = True
        # time match
        time_before = parse_time(self.hass, self.before)
        time_after = parse_time(self.hass, self.after)
        time_matches = time_match(hass=self.hass, before=time_before, after=time_after)
        # condition match
        if self._condition_template:
            cond_matches = templ_match(self.hass, self._condition_template)
        else:
            cond_matches = True
        self._state = time_matches and cond_matches and day_matches
        self.schedule_update_ha_state()
        async_dispatcher_send(self.hass, "schedule_updated", self.schedule_id)
