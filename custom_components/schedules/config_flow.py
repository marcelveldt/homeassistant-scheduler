"""Config flow for this integration."""
import logging

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback, valid_entity_id

from .const import DOMAIN, TITLE

_LOGGER = logging.getLogger(__name__)


def validate_sensor(entity_id):
    """Validate given sensor entity."""
    if not entity_id:
        return True
    return valid_entity_id(entity_id) and entity_id.startswith("binary_sensor.")


class SchedulesConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Return the options flow."""
        return SchedulesOptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            if user_input.get("workday_sensor") == " ":
                user_input["workday_sensor"] = ""  # needed to allow empty value ?!
            # make sure we're only configured once
            if self.hass.config_entries.async_entries(DOMAIN):
                return self.async_abort(reason="already_configured")
            # Validate user input
            if not validate_sensor(user_input.get("workday_sensor")):
                errors["base"] = "invalid_sensor"
            else:
                # finish
                return self.async_create_entry(title=TITLE, data=user_input)

        default_workday_sensor = ""
        for item in self.hass.states.async_entity_ids("binary_sensor"):
            if "workday" in item:
                default_workday_sensor = item
                break

        # Specify items in the order they are to be displayed in the UI
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "workday_sensor", default=default_workday_sensor
                    ): vol.In(
                        [" "] + self.hass.states.async_entity_ids("binary_sensor")
                    )
                }
            ),
            errors=errors,
        )


class SchedulesOptionsFlowHandler(config_entries.OptionsFlow):
    """OptionsFlow handler."""

    def __init__(self, config_entry):
        """Initialize Transmission options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        errors = {}

        if user_input is not None:
            if user_input.get("workday_sensor") == " ":
                user_input["workday_sensor"] = ""  # needed to allow empty value ?!
            if not validate_sensor(user_input.get("workday_sensor")):
                errors["base"] = "invalid_sensor"
            else:
                return self.async_create_entry(title="", data=user_input)

        # default values from data (setup input)
        workday_sensor = self.config_entry.options.get("workday_sensor")
        if workday_sensor is None:
            workday_sensor = self.config_entry.data.get("workday_sensor")

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required("workday_sensor", default=workday_sensor): vol.In(
                        [" "] + self.hass.states.async_entity_ids("binary_sensor")
                    )
                }
            ),
            errors=errors,
        )
