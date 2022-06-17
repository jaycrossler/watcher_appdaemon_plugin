import appdaemon.plugins.hass.hassapi as hass
from datetime import datetime
from os.path import exists

import json
import base64
# NOTE: Make sure AppDaemon config is set to import 'py3-pillow' as an AppDaemon system package
from PIL import Image, UnidentifiedImageError
from string_helpers import *
from Imagery import Imagery

# -----------------------------------------------
# Listen for multiple types of Action messages,
#   then parse and resend them with updates
# -----------------------------------------------

NOTIFICATIONS_BEFORE_ALLOWING_DUPLICATES = 10

# TODO: Figure why there are images sometimes sent to the log, maybe one camera just sending an image? Maybe a log obj?
# TODO: Rename as watcher, add to camera tracking project
# TODO: Move to Zones
# TODO: Delete old images to save space
# TODO: Use SenseAI for faces
# TODO: Add priorities


class MqttCameraIntents(hass.Hass):
    # Internal configuration variables
    _last_notice = ""  # TODO: Move to zone based priority posts
    _messages_sent = 0
    mqtt = None  # MQTT Object to send/receive messages

    # Variables configurable through config settings
    _defaults = {
        'routing': {
            'image_field_name': 'image_b64',
            'dtg_message_format': '%d/%m/%Y %H:%M:%S',
            'dtg_message_format_short': '%H:%M',
            'mqtt_topic_for_camera_intents': "BlueIris / + / Status",
            'mqtt_topic_for_camera_alert_images': "BlueIris/alerts/+",
            'mqtt_publish_to_topic': "homeassistant / camera_intents / description",
            'mqtt_publish_to_for_latest_image': "homeassistant/camera_intents/latest_image",
            'web_path_to_images': "/local/appdaemon_intents/"
        },
        'saving': {
            'save_latest_format': 'latest_{}.jpg',  # Set to None to not save the latest image
            'thumbnails_subdir': 'thumbnails',
            'thumbnail_max_size': 300,
            'path_to_save_images': "/config/www/appdaemon_intents/",
            'days_to_keep_images': None  # delete old files after n days, or None to keep everything
        }
    }
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
        if not self.mqtt.is_client_connected():
            test_failed.append("MQTT client could not connect")

        if len(test_failed):
            for err in test_failed:
                self.log("[ERROR] {}".format(err))
            return False
        else:
            self.log("=======Setup complete and tests have all passed=======")
            return True

    def get_setting(self, d1, d2):
        if d1 in self._settings:
            if d2 in self._settings[d1]:
                return self._settings[d1][d2]
            else:
                self.log('[ERROR] setting {} not found in config.{}'.format(d2, d1))
        else:
            self.log('[ERROR] setting config.{} not found'.format(d1))
        return None

    def set_config_variables(self):
        _config = self.args["config"] or {}
        _merged_config = self._defaults
        _merged_config = merge_dictionaries(_config, _merged_config)
        self._settings = _merged_config  # Import the config settings from apps.yaml and merge with defaults

    def initialize(self):
        # Initialize is called by AppDaemon every time it's reset or turned off and on
        self.mqtt = self.get_plugin_api("MQTT")
        self._last_notice = ""
        self._messages_sent = 0
        self.set_config_variables()

        # Subscribe to all MQTT messages, and then look for the ones that are image-found messages
        self.mqtt.listen_event(self.mqtt_message_received_event, "MQTT_MESSAGE")

        # Show errors if any tests fail
        self.run_tests_on_config()

    def mqtt_message_received_event(self, event_name, data, kwargs):
        # A message was received, handle it if it meets our filters
        try:
            # Local variables:
            _topic_cameras = self.get_setting('routing', 'mqtt_topic_for_camera_intents')
            _topic_images = self.get_setting('routing', 'mqtt_topic_for_camera_alert_images')

            # If this topic matches the camera feed lookup topic, parse that
            _topic = data['topic']
            if does_needle_match_haystack_topic(_topic, _topic_cameras):
                _camera = _topic.split("/")[1]
                _payload = data['payload']
                _payload = _payload.replace('"analysis":}',
                                            '"analysis":{}}')  # Replace this to help test using BlueIris
                self.handle_camera_message(_camera, _payload)

            # If this topic matches the camera image saving event, parse that
            elif does_needle_match_haystack_topic(_topic, _topic_images):
                _camera = _topic.split("/")[2]
                _payload = data['payload']
                _payload = _payload.replace('"analysis":}',
                                            '"analysis":{}}')  # Replace this to help test using BlueIris
                self.handle_image_message(_camera, _payload)

        except KeyError as ex:
            self.log("KeyError trying to extract topic and payload from MQTT Message: {}".format(ex))

    def set_states_from_zone(self, camera_name, zone_id, trigger, payload):
        state = "on" if trigger.lower() == "on" else "off"
        if camera_name == "annke4hd":
            self.set_state("binary_sensor.occupancy_deck", state=state)
        elif camera_name in ["annke1hd", "annke2hd", "reolink5hd"]:
            self.set_state("binary_sensor.occupancy_courtyard", state=state)
        elif camera_name in ["reolink6"]:
            self.set_state("binary_sensor.occupancy_backyard", state=state)
        pass

    # =================================================================

    def handle_camera_message(self, camera_name, payload):

        # Local variables:
        _dtg_format = self.get_setting('routing', 'dtg_message_format')
        _dtg_format_short = self.get_setting('routing', 'dtg_message_format_short')
        _topic_latest = self.get_setting('routing', 'mqtt_publish_to_for_latest_image')
        _topic = self.get_setting('routing', 'mqtt_publish_to_topic')

        _save_to = self.get_setting('saving', 'path_to_save_images')
        _web_path = self.get_setting('saving', 'web_path_to_images')

        self.log("A MQTT message that matched the _camera_ topic pattern was received")
        self._messages_sent += 1
        try:
            # Handle messages like:
            # {"type":"MOTION_A", "trigger":"ON", "memo":"person:65%,person:78%"}
            #
            # Or ones with analysis like:
            # {"type":"MOTION_A", "trigger":"ON", "memo":"person:81%", "analysis":
            #   [{"api":"objects","found":{"success":true,"predictions":
            #     [{"confidence":0.54902047,"label":"laptop","y_min":1736,"x_min":775,"y_max":2456,"x_max":1487},
            #     {"confidence":0.6813332,"label":"person","y_min":1274,"x_min":580,"y_max":2817,"x_max":1389},
            #     {"confidence":0.9031852,"label":"car","y_min":565,"x_min":702,"y_max":1044,"x_max":1553}],
            #     "duration":0}},
            #    {"api":"faces","found":{"success":true,"predictions":
            #     [{"confidence":0.80594426,"userid":"Jay_2","y_min":1354,"x_min":916,"y_max":1662,"x_max":1146}],
            #     "duration":0}}]}

            try:
                # TODO: Check if it's likely JSON format
                payload_obj = json.loads(payload)
            except ValueError:
                self.log("..but the JSON payload threw an exception when it was being parsed by 'json.loads'")
                # self.log(payload)
                return False

            _zone = get_config_var('type', payload_obj, "unknown")
            zone_id = substring_after(_zone, "MOTION_")
            trigger = get_config_var('trigger', payload_obj, "unknown")

            # Get the zone names from the camera titles
            zone_name, zone_short_name = get_zone_name_from_camera_and_zone(camera_name, zone_id)
            if trigger.lower() == "on":
                # If there are any state changes to HA objects, do those now
                self.set_states_from_zone(camera_name, zone_id, trigger, payload_obj)

                # Extract info from the MQTT message
                _memo = get_config_var('memo', payload_obj, "")
                _analysis = get_config_var('analysis', payload_obj, {})

                # If face analysis exists, extract out people from those
                _people, _face_analysis_results = get_face_contents_from_analysis(_analysis)
                # TODO: Use _face_analysis_results to extract size and loc

                # Build the alert message from what was in the picture
                _message, _count = get_image_contents_from_memo(_memo, _people)
                _past_tense = "were" if _count > 1 else "was"

                message = "{} {} seen {}".format(_message, _past_tense, zone_name)
                if message == self._last_notice:
                    self.log("Duplicate message so not broadcast - {}".format(message))
                elif _count > 0:
                    _time = datetime.now().strftime(_dtg_format)
                    _short_time = datetime.now().strftime(_dtg_format_short)

                    message_package = {"message": message, "zone": zone_short_name,
                                       "time": _time, "short_time": _short_time}

                    # Add an image alert URL to the message if one was sent
                    _image_id = add_field_to_path_if_exists(payload_obj, _save_to, 'path')
                    if 'path' in payload_obj:
                        _file_name = payload_obj['path']

                        # A Path to an image was passed in, check if the image actually exists
                        _file_path = posixpath.join(_save_to, _file_name)
                        file_exists = exists(_file_path)

                        if file_exists:
                            image_url = posixpath.join(_web_path, _file_name)

                            # Post a message just of the URL to the latest
                            self.mqtt.mqtt_publish(_topic_latest, image_url)
                            self.log("Published latest alert to {} - {}".format(_topic_latest, image_url))

                            # Add image information to the intent message
                            message_package['image'] = image_url
                        else:
                            self.log("Received a message for {} but the file doesn't exist".format(_file_name))

                    # Send the alert of the full message via MQTT
                    out = json.dumps(message_package)
                    self.mqtt.mqtt_publish(_topic, out)

                    # save that it was the last one sent to reduce duplicates
                    self._last_notice = message
                    self.log("Published to {} - {}".format(_topic, out))
                else:
                    self.log("Something {} - but empty so not publishing".format(message))
            elif trigger.lower() == "Off":
                # Motion turning off
                self.set_states_from_zone(camera_name, zone_id, trigger, payload_obj)
                self.log("Motion off on camera {} in zone {} - {}".format(camera_name, zone_id, zone_name))
            else:
                self.log("Motion unknown on camera {} in zone {} - {}".format(camera_name, zone_id, zone_name))

        except KeyError as ex:
            self.log("KeyError getting camera {} data:".format(camera_name))
            self.log(payload[0:40])
            self.log(ex)
        pass

    def handle_image_message(self, camera_name, payload):
        # Handle messages like:
        # {"image_b64":"2234asdf..", "path":"image123.jpg"}

        try:
            _save_to = self.get_setting('saving', 'path_to_save_images')
            _save_latest_format = self.get_setting('saving', 'save_latest_format')
            _max_size = int(self.get_setting('saving', 'thumbnail_max_size'))

            self.log("A MQTT message that matched the _image_ topic pattern was received")
            self._messages_sent += 1

            # Get the image and path and save a thumbnail if image is valid
            base64_str, path, thumbnail_path, error = self.extract_path_and_image_from_mqtt_message(
                payload, camera_name)

            # Build the path to save the latest alert to
            if _save_latest_format:
                latest_path = posixpath.join(_save_to, _save_latest_format.format("alert.jpg"))
            else:
                latest_path = None

            if error:
                self.log("[ERROR] {}".format(error))
            elif base64_str and path and len(base64_str) > 1000:
                # Handle the image data
                try:
                    with open(path, "wb") as fh:
                        fh.write(base64.b64decode(str(base64_str)))
                        self.log("Saved an image from [{}] to {} - size {}".format(camera_name, path, len(base64_str)))

                    if latest_path:
                        with open(latest_path, "wb") as fh:
                            fh.write(base64.b64decode(str(base64_str)))

                    # TODO: Also save it as latest

                except:
                    self.log("..Tried to save an image that wouldn't work with the base 64 decoder")

                try:
                    # Also create a thumbnail
                    # self.log("...Saving a thumbnail to {}".format(path_thumbnail))
                    img = Image.open(path)
                    img.thumbnail((_max_size, _max_size))
                    img.save(fp=thumbnail_path)
                    # self.log("...Saved a thumbnail also to {}".format(path_thumbnail))

                except UnidentifiedImageError:
                    self.log("..PIL could not import the included image")
                except ValueError:
                    self.log("..ValueError on saving a smaller image, size {}".format(len(base64_str)))

            else:
                self.log("..couldn't save image - no path or b64 image data")

        except KeyError as ex:
            self.log("KeyError problem in handling image message: {}".format(ex))

    def extract_path_and_image_from_mqtt_message(self, payload, camera_name):

        # Local variables:
        path = None
        base64_str = None
        error = None
        thumbnail_path = None

        _b64_field_name = self.get_setting('routing', 'image_field_name')
        _save_latest_format = self.get_setting('saving', 'save_latest_format')
        _thumbnails_subdir = self.get_setting('saving', 'thumbnails_subdir')
        _save_loc = self.get_setting('saving', 'path_to_save_images')

        # If it doesn't start with a { assume it's a b64 encoded image. Generate paths and get the image data
        if payload and len(payload) > 1000 and payload[0] != "{":
            # A large image payload was received that isn't JSON.  See if it's a bit64 image
            path = posixpath.join(_save_loc, _save_latest_format.format(camera_name))
            thumbnail_path = posixpath.join(_save_loc, _thumbnails_subdir, _save_latest_format.format(camera_name))
            base64_str = payload

        elif payload and 'path' in payload and _b64_field_name in payload:
            # This is likely JSON, try to extract and use it
            try:
                payload_obj = json.loads(payload)

                path = add_field_to_path_if_exists(payload_obj, _save_loc, 'path')
                thumbnail_path = add_field_to_path_if_exists(payload_obj, _save_loc, 'path', _thumbnails_subdir)
                base64_str = get_config_var(_b64_field_name, payload_obj, "")
                # self.log("Image {} extracted, size {}".format(path, len(base64_str)))
            except ValueError:
                error = "Received an alert JSON payload that threw an exception"
        else:
            error = "Invalid JSON or image data received"

        return base64_str, path, thumbnail_path, error
