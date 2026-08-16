"""DataUpdateCoordinator for our integration."""

from datetime import timedelta, datetime
from typing import Any
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    #CONF_HOST,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)
from homeassistant.core import DOMAIN, HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import API, APIConnectionError
from .const import DEFAULT_SCAN_INTERVAL, USE_MOCK_DATA
import logging

_LOGGER = logging.getLogger(__name__)

class LuminusCoordinator(DataUpdateCoordinator):
    """My example coordinator."""

    data: list[dict[str, Any]]

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize coordinator."""

        # Set variables from values entered in config flow setup
        self.user = config_entry.data[CONF_USERNAME]
        self.pwd = config_entry.data[CONF_PASSWORD]
        self.config_data = config_entry.data

        # set variables from options.  You need a default here in case options have not been set
        self.poll_interval = config_entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )

        # Initialise DataUpdateCoordinator
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} ({config_entry.unique_id})",
            # Method to call on every update interval.
            update_method=self.async_update_data,
            # Polling interval. Will only be polled if you have made your
            # platform entities, CoordinatorEntities.
            # Using config option here but you can just use a fixed value.
            update_interval=timedelta(seconds=self.poll_interval),
        )

        # Initialise your api here and make available to your integration.
        self.api = API(user=self.user, pwd=self.pwd, mock=USE_MOCK_DATA)

    async def async_update_data(self):
        """Fetch data from API endpoint.

        This is the place to retrieve and pre-process the data into an appropriate data structure
        to be used to provide values for all your entities.
        """
        try:
            # ----------------------------------------------------------------------------
            # Get the data from your api
            # NOTE: Change this to use a real api call for data
            # ----------------------------------------------------------------------------
            
            await self.hass.async_add_executor_job(self.api.login)
            meters = await self.hass.async_add_executor_job(self.api.get_meters)
            data = []
            for meter in meters['meters']:
                ean_nbr = meter['ean']
                energy_type = meter['energyType']
                meter_details = await self.hass.async_add_executor_job(self.api.get_meter, ean_nbr)
                if not meter_details is None:
                    seasonal_prices = meter_details.get('seasonalPrices', {})
                    prices = meter_details.get('prices', {})
                    product_name = meter_details['productName']
                    default_meter_type = "seasonal" if seasonal_prices else meter_details.get('activeMeterType')
                    meter_type = self.config_data.get(ean_nbr) or default_meter_type
                    
                    if meter_type == "seasonal" and seasonal_prices:
                        prices["seasonal"] = seasonal_prices
                        
                    meter_prices = prices[meter_type]
                    device = self.create_device(ean_nbr, product_name, energy_type, meter_type, meter_prices)
                    data.append(device)
                    
            #await self.hass.async_add_executor_job(self.api.logout)
            _LOGGER.info('Data updated.')
            
        except APIConnectionError as err:
            
            if self.data is None:
                _LOGGER.error(err)
                raise UpdateFailed(err) from err
            else:
                _LOGGER.warning('Could not fetch data from Luminus API.')  
                return self.data                            
            #
        except Exception as err:
            if self.data is None:
                # This will show entities as unavailable by raising UpdateFailed exception
                _LOGGER.error(err)
                raise UpdateFailed(f"Error communicating with API: {err}") from err
            else:
                _LOGGER.warning('Could not fetch data from Luminus API.')  
                return self.data                             
            
        # What is returned here is stored in self.data by the DataUpdateCoordinator
        self.data = data
        return data
    
    def create_device(self, ean_nbr: str, product_name: str, energy_type: str, meter_type: str, meter_prices: dict[str, Any]) -> dict[str, Any]:
        device = {
            'device_id': ean_nbr,
            'device_name': f'{product_name} {meter_type} ({ean_nbr})',
            'device_type': energy_type,
            'product_name': product_name,
            'ean': ean_nbr,
            'last_update': datetime.now(),
            'meter_type': meter_type
        }
        for propName, price in meter_prices.items():
            device[propName] = price['rate'] / (1 if propName == 'fixed' else 100)
        
        return device

    # ----------------------------------------------------------------------------
    # Here we add some custom functions on our data coordinator to be called
    # from entity platforms to get access to the specific data they want.
    #
    # These will be specific to your api or yo may not need them at all
    # ----------------------------------------------------------------------------
    def get_device(self, device_id: int) -> dict[str, Any]:
        """Get a device entity from our api data."""
        try:
            return [
                devices for devices in self.data if devices["device_id"] == device_id
            ][0]
        except (TypeError, IndexError):
            # In this case if the device id does not exist you will get an IndexError.
            # If api did not return any data, you will get TypeError.
            return None

    def get_device_parameter(self, device_id: int, parameter: str) -> Any:
        """Get the parameter value of one of our devices from our api data."""
        if device := self.get_device(device_id):
            return device.get(parameter)
