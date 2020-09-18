"""Data storage helper."""
import logging
import time
from collections import OrderedDict
from typing import MutableMapping, cast

import attr
from homeassistant.core import callback
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.loader import bind_hass

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

DATA_REGISTRY = f"{DOMAIN}_storage"

STORAGE_KEY = f"{DOMAIN}.storage"
STORAGE_VERSION = 1
SAVE_DELAY = 10


@attr.s(slots=True, frozen=True)
class ScheduleEntry:
    """Schedule storage Entry."""

    schedule_id = attr.ib(type=str, default=None)
    after = attr.ib(type=str, default=None)
    before = attr.ib(type=str, default=None)
    weekdays = attr.ib(type=list, default=None)
    condition = attr.ib(type=str, default=None)


class ScheduleStorage:
    """Class to hold a registry of schedules."""

    def __init__(self, hass: HomeAssistantType) -> None:
        """Initialize the schedule storage."""
        self.hass = hass
        self.schedules: MutableMapping[str, ScheduleEntry] = {}
        self._store = hass.helpers.storage.Store(STORAGE_VERSION, STORAGE_KEY)

    @callback
    def async_get(self, schedule_id) -> ScheduleEntry:
        """Get an existing ScheduleEntry by id."""
        return self.schedules.get(schedule_id)

    @callback
    def async_create(
        self, schedule_id, after, before, weekdays, condition
    ) -> ScheduleEntry:
        """Create a new ScheduleEntry."""
        if schedule_id in self.schedules:
            schedule_id += " " + str(int(time.time()))
        new_sched = ScheduleEntry(
            schedule_id=schedule_id,
            after=after,
            before=before,
            weekdays=weekdays,
            condition=condition,
        )
        self.schedules[schedule_id] = new_sched
        self.async_schedule_save()
        return new_sched

    @callback
    def async_delete(self, schedule_id: str) -> None:
        """Delete ScheduleEntry."""
        if schedule_id in self.schedules:
            del self.schedules[schedule_id]
            self.async_schedule_save()
            return True
        return False

    @callback
    def async_update(self, schedule_id: str, changes: dict) -> ScheduleEntry:
        """Update existing ScheduleEntry."""
        old = self.schedules[schedule_id]
        new = self.schedules[schedule_id] = attr.evolve(old, **changes)
        self.async_schedule_save()
        return new

    async def async_load(self) -> None:
        """Load the registry of schedule entries."""
        data = await self._store.async_load()
        schedules: "OrderedDict[str, ScheduleEntry]" = OrderedDict()

        if data is not None:
            for schedule in data["schedules"]:
                schedules[schedule["schedule_id"]] = ScheduleEntry(
                    schedule_id=schedule["schedule_id"],
                    after=schedule["after"],
                    before=schedule["before"],
                    weekdays=schedule["weekdays"],
                    condition=schedule.get("condition", None),
                )
        self.schedules = schedules

    @callback
    def async_schedule_save(self) -> None:
        """Schedule saving the registry of schedules."""
        self._store.async_delay_save(self._data_to_save, SAVE_DELAY)

    async def async_save(self) -> None:
        """Save the registry of schedules."""
        await self._store.async_save(self._data_to_save())

    @callback
    def _data_to_save(self) -> dict:
        """Return data for the registry of schedules to store in a file."""
        data = {}
        data["schedules"] = [
            {
                "schedule_id": entry.schedule_id,
                "after": entry.after,
                "before": entry.before,
                "weekdays": entry.weekdays,
                "condition": entry.condition,
            }
            for entry in self.schedules.values()
        ]
        return data


@bind_hass
async def async_get_registry(hass: HomeAssistantType) -> ScheduleStorage:
    """Return schedule storage instance."""
    task = hass.data.get(DATA_REGISTRY)

    if task is None:

        async def _load_reg() -> ScheduleStorage:
            registry = ScheduleStorage(hass)
            await registry.async_load()
            return registry

        task = hass.data[DATA_REGISTRY] = hass.async_create_task(_load_reg())

    return cast(ScheduleStorage, await task)
