"""Sensor which lists the (first) active schedule."""

import datetime
import logging

import homeassistant.util.dt as dt_util
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from . import const
from .util import parse_time

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up sensor from config entry."""
    sensor = ActiveScheduleSensor(hass)
    async_add_entities([sensor])

    @callback
    def async_sensor_callback(schedule_id):
        """Handle callback when a schedule state changes."""
        sensor.schedule_update_ha_state()

    async_dispatcher_connect(hass, "schedule_updated", async_sensor_callback)


class ActiveScheduleSensor(Entity):
    """Representation of the active schedule sensor."""

    def __init__(self, hass):
        """Initialize entity."""
        self.hass = hass

    @property
    def state(self):
        """Return state of the sensor."""
        # simply return the first active schedule
        active_scheds = self.get_all_active_schedules()
        if active_scheds:
            return active_scheds[0]
        return None

    @property
    def should_poll(self):
        """Return a bool if this entity should be actively polled for status."""
        return False

    @callback
    def get_all_active_schedules(self):
        """Return all active scheduleid's as list, sorted by time/date."""
        active_schedules = []
        all_scheds = list(
            self.hass.data[const.DATA_DOMAIN][const.DATA_SCHEDULES].values()
        )
        # sort schedules by time/date and list all active ones
        all_scheds.sort(key=self.__get_after_sort_time)
        all_scheds.sort(key=self.__get_before_sort_time)
        for sched in all_scheds:
            if sched.is_on:
                active_schedules.append(sched.schedule_id)
        return active_schedules

    @property
    def device_state_attributes(self):
        """Return the device specific state attributes."""
        return {const.ATTR_ALL_ACTIVE_SCHEDULES: self.get_all_active_schedules()}

    @property
    def name(self):
        """Return the name of the entity."""
        return "Active Schedule Sensor"

    @property
    def unique_id(self):
        """Return the unique_id of the entity."""
        return "ActiveScheduleSensor"

    def __get_after_sort_time(self, sched):
        """Get the true timestamp for the after-time for sorting."""
        if sched.after is None or sched.before is None:
            return 0
        sched_before = parse_time(self.hass, sched.before)
        sched_after = parse_time(self.hass, sched.after)
        if sched_after > sched_before:
            yesterday = (dt_util.now() - datetime.timedelta(days=1)).date()
            return datetime.datetime.combine(yesterday, sched_after)
        return datetime.datetime.combine(dt_util.now(), sched_after)

    def __get_before_sort_time(self, sched):
        """Get the true timestamp for the before-time for sorting."""
        if sched.after is None or sched.before is None:
            return 0
        sched_before_time = parse_time(self.hass, sched.before)
        sched_before = datetime.datetime.combine(
            datetime.datetime.now(), sched_before_time
        )
        if dt_util.as_local(sched_before) < dt_util.now():
            tomorrow = (dt_util.now() + datetime.timedelta(days=1)).date()
            sched_before = datetime.datetime.combine(tomorrow, sched_before_time)
        return sched_before
