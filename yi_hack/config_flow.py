import logging
import voluptuous as vol

from homeassistant import config_entries

from homeassistant.const import (
    CONF_NAME,
    CONF_HOST,
    CONF_PORT,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_MAC,
)
from homeassistant.helpers.device_registry import format_mac
from homeassistant.components.ffmpeg import CONF_EXTRA_ARGUMENTS

from .config import get_status

from .const import (
    DOMAIN,
    DEFAULT_BRAND,
    DEFAULT_HOST,
    DEFAULT_PORT,
    DEFAULT_USERNAME,
    DEFAULT_PASSWORD,
    DEFAULT_EXTRA_ARGUMENTS,
    CONF_HACK_NAME,
    CONF_SERIAL,
    CONF_PTZ,
)

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = {
    vol.Required(CONF_HOST, default=DEFAULT_HOST): str,
    vol.Required(CONF_PORT, default=DEFAULT_PORT): str,
    vol.Optional(CONF_USERNAME, default=DEFAULT_USERNAME): str,
    vol.Optional(CONF_PASSWORD, default=DEFAULT_PASSWORD): str,
    vol.Optional(CONF_EXTRA_ARGUMENTS, default=DEFAULT_EXTRA_ARGUMENTS): str,
}

class YiHackFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a yi-hack config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_user(self, user_input=None):
        """Handle a flow initiated by the user."""
        errors = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input[CONF_PORT]
            user = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]
            extra_arguments = user_input[CONF_EXTRA_ARGUMENTS]

            auth = None
            if user or password:
                auth = HTTPBasicAuth(user, password)

            response = await self.hass.async_add_executor_job(get_status, user_input)
            if response is not None:
                try:
                    serial_number = response["serial_number"]
                except KeyError:
                    serial_number = None

                try:
                    mac = response["mac_addr"]
                except KeyError:
                    mac = None

                try:
                    ptz = response["ptz"]
                except KeyError:
                    ptz = "no"

                try:
                    hackname = response["name"]
                except KeyError:
                    hackname = DEFAULT_BRAND

                if serial_number is not None and mac is not None:
                    user_input[CONF_SERIAL] = serial_number
                    user_input[CONF_MAC] = format_mac(mac)
                    user_input[CONF_PTZ] = ptz
                    user_input[CONF_HACK_NAME] = hackname
                    user_input[CONF_NAME] = user_input[CONF_HACK_NAME] + "-" + user_input[CONF_MAC].replace(':', '')
                else:
                    _LOGGER.error("Unable to get mac address or serial number from device %s", host)
                    errors["base"] = "cannot_get_mac_or serial"

                if not errors:
                    await self.async_set_unique_id(user_input[CONF_MAC])
                    self._abort_if_unique_id_configured()

                    for entry in self._async_current_entries():
                        if entry.data[CONF_MAC] == user_input[CONF_MAC]:
                            _LOGGER.error("Device already configured: %s", host)
                            return self.async_abort(reason="already_configured")

                    return self.async_create_entry(
                        title=user_input[CONF_NAME],
                        data=user_input
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(DATA_SCHEMA),
            errors=errors,
        )