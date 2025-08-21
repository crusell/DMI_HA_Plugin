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
                # Convert coordinates to float, handling comma format
                try:
                    lat = float(str(user_input[CONF_LATITUDE]).replace(',', '.'))
                    lon = float(str(user_input[CONF_LONGITUDE]).replace(',', '.'))
                except ValueError:
                    errors["base"] = "invalid_coordinates"
                    return self.async_show_form(
                        step_id="user",
                        data_schema=vol.Schema(
                            {
                                vol.Required(CONF_NAME, default=user_input.get(CONF_NAME, DEFAULT_NAME)): str,
                                vol.Required(CONF_API_KEY, default=user_input.get(CONF_API_KEY, "")): str,
                                vol.Required(CONF_LATITUDE, default=user_input.get(CONF_LATITUDE, "")): str,
                                vol.Required(CONF_LONGITUDE, default=user_input.get(CONF_LONGITUDE, "")): str,
                            }
                        ),
                        errors=errors,
                        description_placeholders={
                            "docs_url": "https://www.dmi.dk/data/dmi-opendata/"
                        },
                    )
                
                # Validate coordinates are reasonable
                if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
                    errors["base"] = "invalid_coordinates"
                else:
                    # Create the config entry with converted coordinates
                    config_data = user_input.copy()
                    config_data[CONF_LATITUDE] = lat
                    config_data[CONF_LONGITUDE] = lon
                    
                    return self.async_create_entry(
                        title=user_input[CONF_NAME],
                        data=config_data
                    )
                    
            except Exception as e:
                _LOGGER.error("Config flow error: %s", e)
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
                    vol.Required(CONF_API_KEY): str,
                    vol.Required(CONF_LATITUDE): str,
                    vol.Required(CONF_LONGITUDE): str,
                }
            ),
            errors=errors,
            description_placeholders={
                "docs_url": "https://www.dmi.dk/data/dmi-opendata/"
            },
        )
