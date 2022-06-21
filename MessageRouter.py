import appdaemon.plugins.hass.hassapi as hass
# NOTE: Make sure AppDaemon config is set to import 'py3-pillow' as an AppDaemon system package

from string_helpers import *
from ImageAlertMessage import ImageAlertMessage
from MessageRouterConfiguration import MessageRouterConfiguration
from Zones import Zones

# ---------------------------------------------------
# Listen for multiple types of Image Action messages,
#   then parse and resend them with updates
# ---------------------------------------------------

# TODO: Add in camera tracking project
# TODO: Use SenseAI for faces
# TODO: Add priorities


class MessageRouter(hass.Hass):
    # Internal configuration variables
    _last_notice = ""  # TODO: Move to zone based priority posts
    mqtt = None  # MQTT Object to send/receive messages
    zones = None

    # Variables configurable through config settings
    _settings = {}
    last_message = None

    # =================================================================

    def run_tests_on_config(self):
        test_failed = []

        if int(self.get_setting('saving', 'days_to_keep_images')) != 14:
            test_failed.append("Failed config overriding defaults [savings.days_to_keep_images]. Settings merge?")
        if self.get_setting('saving', 'save_latest_format') != 'latest_{}.jpg':
            test_failed.append("Failed looking up savings.save_latest_format being correct, likely app.yaml problem")
        if self.get_setting('routing', 'image_field_name') != 'image_b64':
            test_failed.append("Failed looking up routing.image_field_name, likely problem parsing _settings")
        if 'zones' not in self._settings:
            test_failed.append("Failed finding config.yaml items in _settings, maybe didn't load")
        elif len(self._settings['zones']) and 'id' in self._settings['zones'] \
                and self._settings['zones'][0]['id'] != 'simulated':
            test_failed.append("First zone in config.yaml is not 'simulated'")

        if not self.mqtt.is_client_connected():
            test_failed.append("MQTT client could not connect")

        if len(test_failed):
            for err in test_failed:
                self.log("[ERROR] {}".format(err), level="ERROR")
            return False
        else:
            self.log("=======Setup complete and tests have all passed=======", level="INFO")
            return True

    def get_setting(self, d1, d2):
        if d1 in self._settings:
            if d2 in self._settings[d1]:
                return self._settings[d1][d2]
            else:
                self.log('[ERROR] the setting {} not found in config.{}'.format(d2, d1), level="ERROR")
        else:
            self.log('[ERROR] the setting config.{} not found'.format(d1), level="ERROR")
        return None

    def set_config_variables(self):
        # Load configuration variables
        _config = self.args["config"] or {}
        _config_from_file = {}
        if "config_file" in _config:
            config_filename = _config["config_file"]
            _config_from_file = load_config_file_node(config_filename, 'config', {}, self.log)

        # Build the configuration - start with defaults, add config pointer file, add apps.yaml settings
        defaults = MessageRouterConfiguration()

        _merged_config = defaults.defaults
        _merged_config = merge_dictionaries(_config_from_file, _merged_config)
        _merged_config = merge_dictionaries(_config, _merged_config)
        self._settings = _merged_config  # Import the config settings from apps.yaml and merge with defaults

    def initialize(self):
        # Initialize is called by AppDaemon every time it's reset or turned off and on
        self.mqtt = self.get_plugin_api("MQTT")
        self._last_notice = ""
        self.set_config_variables()
        self.zones = Zones(settings=self._settings, log=self.log)
        self.last_message = None

        # Subscribe to all MQTT messages, and then look for the ones that are image-found messages
        self.mqtt.listen_event(self.mqtt_message_received_event, "MQTT_MESSAGE")

        # Show errors if any tests fail
        self.run_tests_on_config()

    def mqtt_message_received_event(self, event_name, data, kwargs):
        # A message was received, handle it if it meets our filters
        try:
            self.log("MQTT message received")
            # Local variables:
            _topic_image_alert = self.get_setting('routing', 'mqtt_topic_for_camera_alert_images')

            # If this topic matches the camera alert message, parse that
            _topic = data['topic']
            if does_needle_match_haystack_topic(_topic, _topic_image_alert):
                # Match something like: BlueIris/alerts/cam1
                _camera = _topic.split("/")[2]
                _payload = data['payload']
                _payload = _payload.replace('"analysis":}',
                                            '"analysis":{}}')  # Replace this to help test using BlueIris

                # Pass the payload to an IAM class to begin analysis
                self.last_message = ImageAlertMessage(
                    camera_name=_camera,
                    payload=_payload,
                    zones=self.zones,
                    mqtt_publish=self.mqtt.mqtt_publish,
                    get_entity=self.get_entity,
                    settings=self._settings,
                    log=self.log)

        except KeyError as ex:
            self.log("KeyError trying to extract topic and payload from MQTT Message: {}".format(ex), level="ERROR")
