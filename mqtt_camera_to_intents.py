import os

import appdaemon.plugins.hass.hassapi as hass
import json
from datetime import datetime

import base64
# NOTE: Make sure AppDaemon config is set to import 'py3-pillow' as an AppDaemon system package
from PIL import Image, UnidentifiedImageError
from string_helpers import *

# -----------------------------------------------
# Listen for multiple types of Action messages,
#   then parse and resend them with updates
# -----------------------------------------------

NOTIFICATIONS_BEFORE_ALLOWING_DUPLICATES = 10

# TODO: Figure why there are images sometimes sent to the log, maybe one camera just sending an image? Maybe a log obj?
# TODO: Rename as watcher, add to camera tracking project
# TODO: Move to Zones
# TODO: Verify images exist before posting message
# TODO: Delete old images to save space
# TODO: Use SenseAI for faces
# TODO: Add priorities


class MqttCameraIntents(hass.Hass):
    # Internal configuration variables
    _last_notice = ""  # TODO: Move to zone based priority posts
    _messages_sent = 0
    mqtt = None  # MQTT Object to send/receive messages

    # Variables configurable through config settings
    IMAGE_FIELD_NAME = None
    DTG_MESSAGE_FORMAT = None
    SAVE_LATEST_FORMAT = None
    THUMBNAILS_SUBDIR = None
    THUMBNAILS_MAX_SIZE = None
    MQTT_TOPIC_FOR_CAMERA_INTENTS = None
    MQTT_TOPIC_FOR_CAMERA_ALERT_IMAGES = None
    PUBLISH_TOPIC_MESSAGE = None
    PUBLISH_TOPIC_LATEST_IMAGE = None
    SAVE_BLUEIRIS_LOCATION = None
    WEB_PATH_TO_IMAGES = None

    def set_config_variables(self):
        _config = self.args["config"] or {}
        _routing = get_config_var("routing", _config, {})
        self.IMAGE_FIELD_NAME = get_config_var("image_field_name", _routing, 'image_b64')
        self.DTG_MESSAGE_FORMAT = get_config_var("dtg_message_format", _routing, '%d/%m/%Y %H:%M:%S')
        self.SAVE_LATEST_FORMAT = get_config_var("save_latest_format", _routing, 'latest_{}.jpg')
        self.THUMBNAILS_SUBDIR = get_config_var("thumbnails_subdir", _routing, 'thumbnails')
        self.THUMBNAILS_MAX_SIZE = get_config_var("thumbnail_max_size", _routing, 200)

        self.MQTT_TOPIC_FOR_CAMERA_INTENTS = get_config_var("mqtt_topic_for_camera_intents", _routing, "BlueIris/+/Status")
        self.MQTT_TOPIC_FOR_CAMERA_ALERT_IMAGES = get_config_var("mqtt_topic_for_camera_alert_images", _routing, "BlueIris/alerts/+")
        self.PUBLISH_TOPIC_MESSAGE = get_config_var("mqtt_publish_to_topic", _routing, "homeassistant/camera_intents/description")
        self.PUBLISH_TOPIC_LATEST_IMAGE = get_config_var("mqtt_publish_to_for_latest_image", _routing, "homeassistant/camera_intents/latest_image")
        self.SAVE_BLUEIRIS_LOCATION = get_config_var("path_to_save_images", _routing, "/config/www/appdaemon_intents/")
        self.WEB_PATH_TO_IMAGES = get_config_var("web_path_to_images", _routing, "/local/appdaemon_intents/")

    def initialize(self):
        # Initialize is called by AppDaemon every time it's reset or turned off and on
        self.mqtt = self.get_plugin_api("MQTT")
        self._last_notice = ""
        self._messages_sent = 0
        self.set_config_variables()

        # Subscribe to all MQTT messages, and then look for the ones that are image-found messages
        self.mqtt.listen_event(self.mqtt_message_received_event, "MQTT_MESSAGE")
        if self.mqtt.is_client_connected():
            self.log("================ MQTT client is connected, should be able to send/receive messages")
        else:
            self.log("=[ERROR]====== MQTT client could not connect")

    def mqtt_message_received_event(self, event_name, data, kwargs):
        # A message was received, handle it if it meets our filters
        try:
            _topic = data['topic']

            # If this topic matches the camera feed lookup topic, parse that
            if does_needle_match_haystack_topic(_topic, self.MQTT_TOPIC_FOR_CAMERA_INTENTS):
                _camera = _topic.split("/")[1]
                _payload = data['payload']
                _payload = _payload.replace('"analysis":}',
                                            '"analysis":{}}')  # Replace this to help test using BlueIris
                self.handle_camera_message(_camera, _payload)

            # If this topic matches the camera image saving event, parse that
            elif does_needle_match_haystack_topic(_topic, self.MQTT_TOPIC_FOR_CAMERA_ALERT_IMAGES):
                _camera = _topic.split("/")[2]
                _payload = data['payload']
                _payload = _payload.replace('"analysis":}',
                                            '"analysis":{}}')  # Replace this to help test using BlueIris
                self.handle_image_message(_camera, _payload)

        except KeyError:
            self.log("KeyError trying to extract topic and payload from MQTT Message")

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
        self.log("A MQTT message that matched the _camera_ topic pattern was received")
        self._messages_sent += 1
        try:
            # Handle messages like:
            # {"type":"MOTION_A", "trigger":"ON", "memo":"person:65%,person:78%"}
            # Or ones with analysis like:
            # {"type":"MOTION_A", "trigger":"ON", "memo":"person:81%", "analysis":
            #   [{"api":"objects","found":{"success":true,"predictions":
            #     [{"confidence":0.54902047,"label":"laptop","y_min":1736,"x_min":775,"y_max":2456,"x_max":1487},
            #     {"confidence":0.5561656,"label":"chair","y_min":2193,"x_min":1266,"y_max":2945,"x_max":1976},
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

            _zone = payload_obj['type'] if 'type' in payload_obj else "unknown"
            zone_id = substring_after(_zone, "MOTION_")
            trigger = payload_obj['trigger'] if 'trigger' in payload_obj else "UNKNOWN"

            # Get the zone names from the camera titles
            zone_name, zone_short_name = get_zone_name_from_camera_and_zone(camera_name, zone_id)
            if trigger.lower() == "on":
                # If there are any state changes to HA objects, do those now
                self.set_states_from_zone(camera_name, zone_id, trigger, payload_obj)

                # Extract info from the MQTT message
                _memo = payload_obj['memo'] if 'memo' in payload_obj else ""
                _analysis = payload_obj['analysis'] if 'analysis' in payload_obj else {}

                # If face analysis exists, extract out people from those
                _people, _face_analysis_results = get_face_contents_from_analysis(_analysis)
                # TODO: Use _face_analysis_results to extract size and loc

                # Build the alert message from what was in the picture
                _message, _count = get_image_contents_from_memo(_memo, _people)
                _past_tense = "were" if _count > 1 else "was"

                message = "{} {} seen {}".format(_message, _past_tense, zone_name)
                if _count > 0 and message != self._last_notice:
                    _time = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                    _short_time = datetime.now().strftime("%H:%M")

                    message_package = {"message": message, "zone": zone_short_name,
                                       "time": _time, "short_time": _short_time}

                    # Add an image alert URL to the message if one was sent
                    _image_id = add_field_to_path_if_exists(payload_obj, self.SAVE_BLUEIRIS_LOCATION, 'path')
                    if 'path' in payload_obj:
                        image_url = posixpath.join(self.WEB_PATH_TO_IMAGES, payload_obj['path'])
                        message_package['image'] = image_url

                        # TODO: Check if the image actually exists

                        # Post a message just of the URL to the latest
                        self.mqtt.mqtt_publish(self.PUBLISH_TOPIC_LATEST_IMAGE, image_url)
                        self.log("Published latest alert to {} - {}".format(self.PUBLISH_TOPIC_LATEST_IMAGE, image_url))

                    # Send the alert of the full message via MQTT
                    out = json.dumps(message_package)
                    self.mqtt.mqtt_publish(self.PUBLISH_TOPIC_MESSAGE, out)

                    # save that it was the last one sent to reduce duplicates
                    self._last_notice = message
                    self.log("Published to {} - {}".format(self.PUBLISH_TOPIC_MESSAGE, out))
                elif _count > 0:
                    self.log("Duplicate message so not broadcast - {}".format(message))
                else:
                    self.log("Something {} - but empty so not publishing".format(message))
            elif trigger == "OFF":
                # Motion turning off
                # TODO: Turn off motion if sensor occupancy item set
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

        self.log("A MQTT message that matched the _image_ topic pattern was received")
        self._messages_sent += 1

        # Get the image and path and save a thumbnail if image is valid
        base64_str, path, thumbnail_path, error = extract_path_and_image_from_mqtt_message(
            payload, self.SAVE_BLUEIRIS_LOCATION, camera_name)

# TODO: add these variables:

#            b64_field_name=self.IMAGE_FIELD_NAME,
#            save_latest_format=self.SAVE_LATEST_FORMAT, thumbnails_subdir=self.THUMBNAILS_SUBDIR

        # Build the path to save the latest alert to
        if self.SAVE_LATEST_FORMAT:
            latest_path = posixpath.join(self.SAVE_BLUEIRIS_LOCATION, self.SAVE_LATEST_FORMAT.format("alert.jpg"))
        else:
            latest_path = None

        if error:
            self.log("[ERROR] {}".format(error))
        elif base64_str and path and len(base64_str) > 1000:
            # Handle the image data
            try:
                with open(path, "wb") as fh:
                    fh.write(base64.b64decode(str(base64_str)))
                    self.log("Saved an image from camera [{}] to {} - size {}".format(camera_name, path, len(base64_str)))

                if latest_path:
                    with open(latest_path, "wb") as fh:
                        fh.write(base64.b64decode(str(base64_str)))

            except:
                self.log("..Tried to save an image that wouldn't work with the base 64 decoder")

            try:
                # Also create a thumbnail
                # self.log("...Saving a thumbnail to {}".format(path_thumbnail))
                img = Image.open(path)
                img.thumbnail((self.THUMBNAILS_MAX_SIZE, self.THUMBNAILS_MAX_SIZE))
                img.save(fp=thumbnail_path)
                # self.log("...Saved a thumbnail also to {}".format(path_thumbnail))

            except UnidentifiedImageError:
                self.log("..PIL could not import the included image")
            except ValueError:
                self.log("..ValueError on saving a smaller image, size {}".format(len(base64_str)))

        else:
            self.log("..couldn't save image - no path or b64 image data")
