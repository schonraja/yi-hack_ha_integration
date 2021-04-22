import logging
import requests
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

from requests.auth import HTTPBasicAuth, HTTPDigestAuth

from functools import partial

from .const import (
    DOMAIN,
    DEFAULT_BRAND,
    DEFAULT_HOST,
    DEFAULT_PORT,
    DEFAULT_USERNAME,
    DEFAULT_PASSWORD,
    DEFAULT_EXTRA_ARGUMENTS,
    CONF_SERIAL,
    CONF_RTSP_PORT,
    CONF_MQTT_PREFIX,
    CONF_TOPIC_STATUS,
    CONF_TOPIC_MOTION_DETECTION,
    CONF_TOPIC_BABY_CRYING,
    CONF_TOPIC_MOTION_DETECTION_IMAGE,
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

            try:
                response = requests.get("http://" + host + ":" + port + "/cgi-bin/status.json", timeout=5, auth=auth)
                if response.status_code >= 300:
                    _LOGGER.error("Failed to connect to device %s", host)
                    errors["base"] = "cannot_connect"
            except requests.exceptions.RequestException as error:
                _LOGGER.error("Failed to connect to device %s: error %s", host, error)
                errors["base"] = "cannot_connect"

            if not errors and response is not None:
                try:
                    serial_number = response.json()["serial_number"]
                except KeyError:
                    serial_number = None

                try:
                    mac = response.json()["mac_addr"]
                except KeyError:
                    mac = None

                if serial_number is not None and mac is not None:
                    user_input[CONF_SERIAL] = serial_number
                    user_input[CONF_MAC] = format_mac(mac)
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
                    try:
                        name = response.json()["name"]
                    except KeyError:
                        name = None

                    if name is not None:
                        user_input[CONF_NAME] = name
                    else:
                        user_input[CONF_NAME] = DEFAULT_BRAND
                    user_input[CONF_NAME] = user_input[CONF_NAME] + "-" + user_input[CONF_MAC].replace(':', '')

                    try:
                        response = requests.get("http://" + host + ":" + port + "/cgi-bin/get_configs.sh?conf=system", timeout=5, auth=auth)
                        if response.status_code >= 300:
                            _LOGGER.error("Failed to get configuration from device %s", host)
                            errors["base"] = "cannot_get_conf"
                    except requests.exceptions.RequestException as error:
                        _LOGGER.error("Failed to get configuration from device %s: error %s", host, error)
                        errors["base"] = "cannot_get_conf"

                    if not errors and response is not None:
                        conf = response.json()

                        try:
                            response = requests.get("http://" + host + ":" + port + "/cgi-bin/get_configs.sh?conf=mqtt", timeout=5, auth=auth)
                            if response.status_code >= 300:
                                _LOGGER.error("Failed to get mqtt configuration from device %s", host)
                                errors["base"] = "cannot_get_mqtt_conf"
                        except requests.exceptions.RequestException as error:
                            _LOGGER.error("Failed to get mqtt configuration from device %s: error %s", host, error)
                            errors["base"] = "cannot_get_mqtt_conf"

                        if not errors and response is not None:
                            mqtt = response.json()

                            user_input[CONF_RTSP_PORT] = conf[CONF_RTSP_PORT]
                            user_input[CONF_MQTT_PREFIX] = mqtt[CONF_MQTT_PREFIX]
                            user_input[CONF_TOPIC_STATUS] = mqtt[CONF_TOPIC_STATUS]
                            user_input[CONF_TOPIC_MOTION_DETECTION] = mqtt[CONF_TOPIC_MOTION_DETECTION]
                            user_input[CONF_TOPIC_BABY_CRYING] = mqtt[CONF_TOPIC_BABY_CRYING]
                            user_input[CONF_TOPIC_MOTION_DETECTION_IMAGE] = mqtt[CONF_TOPIC_MOTION_DETECTION_IMAGE]

                            return self.async_create_entry(
                                title=user_input[CONF_NAME],
                                data=user_input
                            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(DATA_SCHEMA),
            errors=errors,
        )