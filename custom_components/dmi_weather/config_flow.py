"""Config flow for DMI Weather integration."""
from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.data_entry_flow import FlowResult
from typing import Any

from .const import DEFAULT_NAME, DOMAIN, CONF_API_KEY
from .dmi_api import DMIWeatherAPI


class DMIWeatherConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for DMI Weather."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                # Test the API connection
                api = DMIWeatherAPI(
                    self.hass,
                    user_input[CONF_LATITUDE],
                    user_input[CONF_LONGITUDE],
                    user_input[CONF_API_KEY]
                )
                
                # Try to get collections to validate API key and connection
                collections = await api._get_collections()
                if not collections:
                    errors["base"] = "cannot_connect"
                else:
                    # Create the config entry
                    return self.async_create_entry(
                        title=user_input[CONF_NAME],
                        data=user_input
                    )
                    
            except Exception:
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
                    vol.Required(CONF_API_KEY): str,
                    vol.Required(CONF_LATITUDE): float,
                    vol.Required(CONF_LONGITUDE): float,
                }
            ),
            errors=errors,
            description_placeholders={
                "docs_url": "https://www.dmi.dk/data/dmi-opendata/"
            },
        )
