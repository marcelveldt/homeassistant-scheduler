"""Utiliies and helpers."""
from datetime import datetime as datetime_sys
from datetime import time as time_sys
from datetime import timedelta
from typing import List, TypeVar, Union, cast

import homeassistant.helpers.config_validation as cv
import homeassistant.util.dt as dt_util
import voluptuous as vol
from homeassistant.const import SUN_EVENT_SUNRISE, SUN_EVENT_SUNSET, WEEKDAYS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.sun import get_astral_event_date

# typing typevar
T = TypeVar("T")


def parse_template(condition_str):
    """Parse a templated condition string."""
    return cv.template(condition_str)


def validate_condition_str(condition_str):
    """Validate a (templated) condition string."""
    if condition_str is None:
        return condition_str
    try:
        cv.template(condition_str)
        return condition_str
    except vol.Invalid as exc:
        raise exc


def validate_time_str(time_str):
    """Validate the given time string."""
    time_str = time_str.strip()
    if time_str.strip() in [SUN_EVENT_SUNRISE, SUN_EVENT_SUNSET]:
        return time_str
    if SUN_EVENT_SUNRISE in time_str or SUN_EVENT_SUNSET in time_str:
        # sunset/sunrise with offset
        if "+" in time_str:
            offset_operator = "+"
        else:
            offset_operator = "-"
        check_time_str = time_str.split(offset_operator)[1].strip()
        if validate_time_str(check_time_str):
            return time_str
    else:
        # timestring in 00:00:00 format
        if dt_util.parse_time(time_str):
            return time_str
    raise vol.Invalid(f"invalid time string: {time_str}")


def parse_sun_event(hass: HomeAssistant, time_str: str):
    """Parse sun condition/event from time string."""
    if not (SUN_EVENT_SUNRISE in time_str or SUN_EVENT_SUNSET in time_str):
        raise ValueError("%s is not a valid sun_event!" % time_str)
    # parse offset if present
    if "+" in time_str:
        sun_event, offset_str = time_str.split("+")
        offset_time = parse_time(hass, offset_str)
        offset = timedelta(
            hours=offset_time.hour,
            minutes=offset_time.minute,
            seconds=offset_time.second,
        )
    elif "-" in time_str:
        sun_event, offset_str = time_str.split("-")
        offset_time = parse_time(hass, offset_str)
        offset = timedelta(
            hours=-offset_time.hour,
            minutes=-offset_time.minute,
            seconds=-offset_time.second,
        )
    else:
        sun_event = time_str
        offset = timedelta()
    return sun_event.strip(), offset


def parse_time(hass: HomeAssistant, time_str: str) -> time_sys:
    """Transform timestring into time object."""
    time_val = None
    time_str = str(time_str)
    time_str = time_str.strip()

    if SUN_EVENT_SUNRISE in time_str or SUN_EVENT_SUNSET in time_str:
        # timestring with sun event (with or without offset)
        utcnow = dt_util.utcnow()
        today = dt_util.as_local(utcnow).date()
        tomorrow = dt_util.as_local(utcnow + timedelta(days=1)).date()

        # parse sun event and offset
        sun_event, offset = parse_sun_event(hass, time_str)

        if sun_event == SUN_EVENT_SUNRISE:
            # grab correct time for sunrise
            time_val = get_astral_event_date(hass, SUN_EVENT_SUNRISE, today)
            if today > dt_util.as_local(cast(datetime_sys, time_val)).date():
                time_val = get_astral_event_date(hass, SUN_EVENT_SUNRISE, tomorrow)
        elif sun_event == SUN_EVENT_SUNSET:
            # grab correct time for sunset
            time_val = get_astral_event_date(hass, SUN_EVENT_SUNSET, today)
            if today > dt_util.as_local(cast(datetime_sys, time_val)).date():
                time_val = get_astral_event_date(hass, SUN_EVENT_SUNRISE, tomorrow)
        else:
            raise ValueError("Error parsing time string: %s" % time_str)
        # append offset to time_val
        time_val = time_val + offset
        # translate utc to local
        time_val = dt_util.as_local(time_val)
        # we only want the time object
        time_val = time_val.time()
    else:
        # regular timestring 00:00:00
        time_val = dt_util.parse_time(time_str)
    return time_val


def ensure_list(value: Union[T, List[T], None]) -> List[T]:
    """Wrap value in list if it is not one."""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [item.strip() for item in value.split(",")]


ALLOWED_WEEKDAYS = WEEKDAYS + ["workday", "not_workday"]
validate_weekdays = vol.All(ensure_list, [vol.In(ALLOWED_WEEKDAYS)])
