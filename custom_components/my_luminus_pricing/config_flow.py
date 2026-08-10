"""Config flows for our integration.
https://developers.home-assistant.io/docs/data_entry_flow_index/#labels--descriptions
"""

from __future__ import annotations
from typing import Any
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import (
    CONF_CHOOSE,
    CONF_DESCRIPTION,
    CONF_HOST,
    CONF_MINIMUM,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_SENSORS,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import selector

from .utils import camel_to_snake_case
from .api import API, APIAuthError, APIConnectionError
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN, MIN_SCAN_INTERVAL, USE_MOCK_DATA
import logging
import voluptuous as vol
#from .coordinator import LuminusCoordinator

_LOGGER = logging.getLogger(__name__)

# ----------------------------------------------------------------------------
# Adjust the data schema to the data that you need
# ----------------------------------------------------------------------------
STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME, description={"suggested_value": ""}): str,
        vol.Required(CONF_PASSWORD, description={"suggested_value": ""}): str,
    }
)

async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    try:
        # ----------------------------------------------------------------------------
        # If your api is not async, use the executor to access it
        # If you cannot connect, raise CannotConnect
        # If the authentication is wrong, raise InvalidAuth
        # ----------------------------------------------------------------------------
        api = API(data[CONF_USERNAME], data[CONF_PASSWORD], mock=USE_MOCK_DATA)
        await hass.async_add_executor_job(api.login)
    except APIAuthError as err:
        raise InvalidAuth from err
    except APIConnectionError as err:
        raise CannotConnect from err
    return {"title": f"Luminus - {data[CONF_USERNAME]}", "api": api}



async def validate_settings(hass: HomeAssistant, data: dict[str, Any]) -> bool:
    """Validate meters config."""
    return True


class LuminusConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Example Integration."""

    VERSION = 1
    MINOR_VERSION = 2
    def __init__(self):
        _input_data: dict[str, Any]
        _title: str
        _reconfigure_flow: bool = False

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step.

        Called when you initiate adding an integration via the UI
        """

        errors: dict[str, str] = {}

        if user_input is not None:
            # The form has been filled in and submitted, so process the data provided.
            try:
                # ----------------------------------------------------------------------------
                # Validate that the setup data is valid and if not handle errors.
                # You can do any validation you want or no validation on each step.
                # The errors["base"] values match the values in your strings.json and translation files.
                # ----------------------------------------------------------------------------
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

            if "base" not in errors:
                # Validation was successful, so proceed to the next step.

                # ----------------------------------------------------------------------------
                # Setting our unique id here just because we have the info at this stage to do that
                # and it will abort early on in the process if alreay setup.
                # You can put this in any step however.
                # ----------------------------------------------------------------------------
                await self.async_set_unique_id(info.get("title"))
                self._abort_if_unique_id_configured()

                # Set our title variable here for use later
                self._title = info["title"]
                self._api = info["api"]
                self._reconfigure_flow = False
                # ----------------------------------------------------------------------------
                # You need to save the input data to a class variable as you go through each step
                # to ensure it is accessible across all steps.
                # ----------------------------------------------------------------------------
                self._input_data = user_input

                # Call the next step                
                #return self.async_create_entry(title=self._title, data=self._input_data)
                return await self.async_step_settings()

        # Show initial form.
        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            description_placeholders={"name": "Add Luminus integration"},
            errors=errors,
            last_step=False,  # Adding last_step True/False decides whether form shows Next or Submit buttons
        )

    async def async_step_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the second step.

        Our second config flow step.
        Works just the same way as the first step.
        Except as it is our last step, we create the config entry after any validation.
        """

        errors: dict[str, str] = {}

        if user_input is not None:
            # The form has been filled in and submitted, so process the data provided.
            if not await validate_settings(self.hass, user_input):
                errors["base"] = "invalid_settings"

            if "base" not in errors:
                # ----------------------------------------------------------------------------
                # Validation was successful, so create the config entry.
                # ----------------------------------------------------------------------------
                
                #Convert dropdown selections back to camel case for use in tariff selection (json key).
                for meter in self.meters:
                    ean_nbr = meter['ean']
                    option = user_input[ean_nbr]
                    user_input[ean_nbr] = meter['meter_types'][option]
                    
                if self._reconfigure_flow:
                    config_entry = self.hass.config_entries.async_get_entry(
                        self.context["entry_id"]
                    )
                    self._reconfigure_flow = False
                    return self.async_update_reload_and_abort(
                        config_entry,
                        unique_id=config_entry.unique_id,
                        data={**config_entry.data, **user_input},
                        reason="reconfigure_successful",
                    )
                else:
                    self._input_data.update(user_input)
                    return self.async_create_entry(title=self._title, data=self._input_data)

        # ----------------------------------------------------------------------------
        # Show settings form.  The step id always needs to match the bit after async_step_ in your method.
        # Set last_step to True here if it is last step.
        # ----------------------------------------------------------------------------
        # coordinator: LuminusCoordinator = self.hass.data[DOMAIN][
            # self.config_entry.entry_id
        # ].coordinator
         # coordinator.data
        
        dynamic_fields = {}
        meters = await self.hass.async_add_executor_job(self._api.get_meters)
        self.meters = meters['meters']
        for meter in meters['meters']:
            ean_nbr = meter['ean']
            energy_type = meter['energyType']
            meter_details = await self.hass.async_add_executor_job(self._api.get_meter, ean_nbr)
            seasonal_prices = meter_details.get('seasonalPrices', {})
            prices = meter_details.get('prices', {})
            if seasonal_prices:
                prices["seasonal"] = seasonal_prices
            
            product_name = meter_details['productName']
            defaultMeterType = self._input_data.get(ean_nbr) or ('seasonal' if seasonal_prices else meter_details.get('activeMeterType'))
            #Convert to snake case for HACS translation keys.
            meter_types = {}
            for meter_type, meter_prices in prices.items():
                meter_type_sc = camel_to_snake_case(meter_type)
                meter_types[meter_type_sc] = meter_type
            meter['meter_types'] = meter_types
            dynamic_fields[vol.Required(ean_nbr, default=camel_to_snake_case(defaultMeterType))] = selector({
                "select": {
                    "options": list(meter_types.keys()),
                    "mode": "dropdown",
                    "sort": True,
                    "translation_key": "meter_type_selector"
                }
            })
        
        return self.async_show_form(
            step_id="settings",
            data_schema=vol.Schema(dynamic_fields),
            errors=errors,
            last_step=True,
        )


    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add reconfigure step to allow to reconfigure a config entry.

        This methid displays a reconfigure option in the integration and is
        different to options.
        It can be used to reconfigure any of the data submitted when first installed.
        This is optional and can be removed if you do not want to allow reconfiguration.
        """
        errors: dict[str, str] = {}
        config_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        
        self._reconfigure_flow = True
        info = await validate_input(self.hass, config_entry.data)
        self._title = info["title"]
        self._api = info["api"]
        self._input_data = config_entry.data
        return await self.async_step_settings()

class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
