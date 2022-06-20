import appdaemon.plugins.hass.hassapi as hass
# NOTE: Make sure AppDaemon config is set to import 'py3-pillow' as an AppDaemon system package

from string_helpers import *
from ImageAlert import ImageAlert
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
    _messages_sent = 0
    mqtt = None  # MQTT Object to send/receive messages
    zones = None

    # Variables configurable through config settings
    _settings = {}

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
        elif len(self._settings['zones']) and 'id' in self._settings['zones'] and self._settings['zones'][0]['id'] != 'simulated':
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
        self._messages_sent = 0
        self.set_config_variables()
        self.zones = Zones(settings=self._settings, log=self.log, set_state=self.set_state)

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
                self.handle_image_alert_message(_camera, _payload)

        except KeyError as ex:
            self.log("KeyError trying to extract topic and payload from MQTT Message: {}".format(ex), level="ERROR")

    # =================================================================

    def handle_image_alert_message(self, camera_name, payload):
        # Handle messages send from a tool like Blue Iris that contains alert and possibly image data

        try:
            self.log("A MQTT message that matched the _image_alert_ topic pattern was received", level="INFO")

            _topic_latest = self.get_setting('routing', 'mqtt_publish_to_for_latest_image')
            _topic_ha_alert = self.get_setting('routing', 'mqtt_publish_to_topic')

            # Create the main ImageAlert object
            image_alert = ImageAlert(camera_name, payload, self._settings, self.log)

            # Trigger any HA actions based on the message contents
            if image_alert.trigger and image_alert.trigger.lower() in ["on", "off"]:
                # If there are any state changes to HA objects, do those now
                self.zones.update_state_for_camera(
                    camera=image_alert.camera_name,
                    trigger=image_alert.trigger,
                    motion_area=image_alert.motion_area)

            else:
                self.log("Unknown trigger state {} - {} - {}".format(
                    image_alert.camera_name, image_alert.motion_area, image_alert.trigger), level="INFO")

            # If the message had an image, create an image object and save it to disk
            if image_alert.image:
                image = image_alert.image

                # Save images as necessary
                image.save_full_sized()
                image.save_thumbnail()
                image.save_as_latest()

                # Post a message just of the URL to the 'latest' topic
                if image.web_url:
                    self.mqtt.mqtt_publish(_topic_latest, image.web_url)
                    self.log("Published latest alert to {} - {}".format(_topic_latest, image.web_url), level="INFO")

                # Remove old images to save disk space
                image.clean_image_folders()

            # TODO: Handle expected objects and have it return messaging if expectations changed
            self.zones.check_expected_areas_for_matches(
                camera=camera_name,
                motion_area=image_alert.motion_area,
                image_alert=image_alert
            )

            # Send the message if it's new
            # TODO: Incorporate priority and new zones text
            _message_text = image_alert.message_text_to_send_to_ha
            if _message_text == self._last_notice:
                self.log("Duplicate message so not broadcast - {}".format(_message_text), level="DEBUG")
            elif image_alert.count_of_important_things > 0:
                # Send a JSON package of the image alert for HA to use
                message = image_alert.message_json_to_send_to_ha()
                self.mqtt.mqtt_publish(_topic_ha_alert, message)

                # Save that it was the last one sent to reduce duplicates
                self._last_notice = image_alert.message_text_to_send_to_ha
                self.log("Published to {} - {}".format(_topic_ha_alert, message), level="INFO")
                self._messages_sent += 1
            else:
                self.log("Something {} - but empty so not publishing".format(_message_text), level="DEBUG")

        except KeyError as ex:
            self.log("KeyError problem in handling image message: {}".format(ex), level="ERROR")
