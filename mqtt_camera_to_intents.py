import os

import appdaemon.plugins.hass.hassapi as hass
import json

import base64
from PIL import Image, UnidentifiedImageError  # NOTE: Make sure AppDaemon config is set to import 'py3-pillow' as a system package
from string_helpers import *

# -----------------------------------------------
# Listen for multiple types of Action messages,
#   then parse and resend them with updates
# -----------------------------------------------

MQTT_TOPIC_FOR_CAMERA_INTENTS = "BlueIris/+/Status"
MQTT_TOPIC_FOR_CAMERA_ALERT_IMAGES = "BlueIris/alerts/+"
PUBLISH_TOPIC = "homeassistant/camera_intents/description"
SAVE_BLUEIRIS_LOCATION = "/config/www/appdaemon_intents/"
NOTIFICATIONS_BEFORE_ALLOWING_DUPLICATES = 10

# TODO: Move these to be within the main class


class MqttCameraIntents(hass.Hass):

    def initialize(self):
        self.mqtt = self.get_plugin_api("MQTT")
        self._last_notice = ""
        self._messages_sent = 0

        # Only seems to work with specific topics, no wildcards -
        #   described in https://buildmedia.readthedocs.org/media/pdf/appdaemon/stable/appdaemon.pdf
        self.mqtt.listen_event(self.mqtt_message_received_event, "MQTT_MESSAGE")
        if self.mqtt.is_client_connected():
            self.log("MQTT is connected")

        self.log("===============================MqttCameraIntents initialized")

    def mqtt_message_received_event(self, event_name, data, kwargs):
        try:
            # Remove the last sent message every few mqtt messages # TODO: Change to be time delay based
            self._messages_sent += 1
            if self._messages_sent % 1 == NOTIFICATIONS_BEFORE_ALLOWING_DUPLICATES:
                self._last_notice = ""

            _topic = data['topic']
            _payload = data['payload']
            _payload = _payload.replace('"analysis":}', '"analysis":{}}')  # Replace this to allow testing in BlueIris

            # If this topic matches the camera feed lookup list, parse that
            if does_needle_match_haystack_topic(_topic, MQTT_TOPIC_FOR_CAMERA_INTENTS):
                _camera = _topic.split("/")[1]
                self.handle_camera_message(_camera, _payload)

            # If this topic matches the camera image saving event, parse that
            elif does_needle_match_haystack_topic(_topic, MQTT_TOPIC_FOR_CAMERA_ALERT_IMAGES):
                _camera = _topic.split("/")[2]
                self.handle_image_message(_camera, _payload)

        except KeyError:
            self.log("KeyError trying to extract topic and payload from MQTT Message")

    def set_states_from_zone(self, camera_name, zone_id, trigger, payload):
        if camera_name == "annke4hd":
            self.set_state("binary_sensor.occupancy_deck", state="on")
        elif camera_name in ["annke1hd", "annke2hd", "reolink5hd"]:
            self.set_state("binary_sensor.occupancy_courtyard", state="on")
        pass

    # =================================================================

    def handle_camera_message(self, camera_name, payload):
        self.log("A MQTT message that matched the camera pattern was received")
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
                payload_obj = json.loads(payload)
            except:
                self.log("Received a JSON payload that threw an exception")
                # self.log(payload)
                payload_obj = {}

            _zone = payload_obj['type'] if 'type' in payload_obj else "unknown"
            zone_id = substring_after(_zone, "MOTION_")
            trigger = payload_obj['trigger'] if 'trigger' in payload_obj else "UNKNOWN"

            # Get the zone names from the camera titles
            zone_name, zone_short_name = get_zone_name_from_camera_and_zone(camera_name, zone_id)
            if trigger == "ON":
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
                    message_package = {"message": message, "zone": zone_short_name}

                    # Add an image alert URL to the message if one was sent
                    _image_id = add_field_to_path_if_exists(payload_obj, SAVE_BLUEIRIS_LOCATION, 'path')
                    if 'path' in payload_obj:
                        message_package['image'] = "/local/appdaemon_intents/" + payload_obj['path']

                    # Send the alert via MQTT
                    out = json.dumps(message_package)
                    self.mqtt.mqtt_publish(PUBLISH_TOPIC, out)

                    # save that it was the last one sent to reduce duplicates
                    self._last_notice = message
                    self.log("Published to {} - {}".format(PUBLISH_TOPIC, out))
                elif _count > 0:
                    self.log("Duplicate message so not broadcast - {}".format(message))
                else:
                    self.log("Something {} - but empty so not publishing".format(message))
            elif trigger == "OFF":
                # Motion turning off
                self.log("Motion off on camera {} in zone {} - {}".format(camera_name, zone_id, zone_name))
            else:
                self.log("Motion unknown on camera {} in zone {} - {}".format(camera_name, zone_id, zone_name))

        except KeyError as ex:
            self.log("KeyError getting camera {} data:".format(camera_name))
            self.log(payload)
            self.log(ex)
        pass

    def handle_image_message(self, camera_name, payload):
        # Handle messages like:
        # {"image_b64":"2234asdf..", "path":"image123.jpg"}

        self.log("A MQTT message that matched the image pattern was received")

        try:
            payload_obj = json.loads(payload)
        except:
            self.log("Received an alert JSON payload that threw an exception")
            payload_obj = {}

        path = add_field_to_path_if_exists(payload_obj, SAVE_BLUEIRIS_LOCATION, 'path')
        base64_str = payload_obj['image_b64'] if 'image_b64' in payload_obj else ""
        self.log("Image {} extracted, size {}".format(path, len(base64_str)))

        if base64_str and path and len(base64_str) > 1000:
            with open(path, "wb") as fh:
                fh.write(base64.b64decode(str(base64_str)))

            self.log("Saved an image from camera [{}] to {} - size {}".format(camera_name, path, len(base64_str)))

            try:
                # Also create a thumbnail
                img = Image.open(path)
                img.thumbnail((120, 120))
                img.save(fp="thumbnail_{}".format(path))
                self.log("...Saved a thumbnail also")

            except UnidentifiedImageError:
                self.log("..PIL could not import the included image")
            except ValueError:
                self.log("..ValueError on saving a smaller image, size {}".format(len(base64_str)))

        else:
            self.log("..couldn't save image - no path or b64 image data")
