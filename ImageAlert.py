import json
from string_helpers import *
from Imagery import Imagery
from datetime import datetime


class ImageAlert:

    def __init__(self, camera_name, payload, settings, log):
        self.camera_name = camera_name
        self._settings = settings
        self._log = log

        self.image = None
        self.motion_area = None
        self.zone_name = None
        self.zone_short_name = None
        self.trigger = None
        self.payload_obj = None
        self.memo = None
        self.analysis = None
        self.message_text_to_send_to_ha = None
        self.count_of_important_things = 0

        self.interpret_camera_message(camera_name, payload)

    def interpret_camera_message(self, camera_name, payload):
        # Interpret JSON messages that have alerts in them and possibly images

        try:
            # TODO: Check if it's likely JSON format
            self.payload_obj = json.loads(payload)
        except ValueError as ex:
            self.log("JSON exception {} when parsed by 'json.loads'".format(ex), level="ERROR")
            self.log(payload[0:40])
            return False

        try:
            # Local variables:
            _topic_latest = self.get_setting('routing', 'mqtt_publish_to_for_latest_image')
            _topic = self.get_setting('routing', 'mqtt_publish_to_topic')

            _motion_area = get_config_var('type', self.payload_obj, "unknown")
            self.motion_area = substring_after(_motion_area, "MOTION_")
            self.trigger = get_config_var('trigger', self.payload_obj, "unknown")

            # Get the zone names from the camera titles
            self.zone_name, self.zone_short_name = get_zone_name_from_camera_and_zone(camera_name, self.motion_area)

            self.memo = get_config_var('memo', self.payload_obj, "")
            self.analysis = get_config_var('analysis', self.payload_obj, {})

            # If face analysis exists, extract out people from those
            _people, _face_analysis_results = get_face_contents_from_analysis(self.analysis)
            # TODO: Use _face_analysis_results to extract size and loc

            # Build the alert message from what was in the picture
            _message, _count = get_image_contents_from_memo(self.memo, _people)
            _past_tense = "were" if _count > 1 else "was"

            self.message_text_to_send_to_ha = "{} {} seen {}".format(_message, _past_tense, self.zone_name)
            self.count_of_important_things = _count

            # Get the image and path and save a thumbnail if image is valid
            base64_str, file_id = self.extract_image_data_from_payload(payload, camera_name)
            if base64_str and file_id:
                # Create an Imagery object and save the files to disk
                self.image = Imagery(
                    file_id=file_id,
                    payload=base64_str,
                    camera=camera_name,
                    settings=self._settings,
                    log=self.log
                )

                # To save memory, don't save the full payload and obj - remove the image piece
                _image_field = self.get_setting("routing", "image_field_name")
                if _image_field in self.payload_obj:
                    del self.payload_obj[_image_field]

        except KeyError as ex:
            self.log("KeyError {} getting camera {} data: {}...".format(ex, camera_name, payload[0:40]), level="ERROR")
        pass

    def message_json_to_send_to_ha(self):
        # Prepare a message in JSON format to send to Home Assistant with useful details

        _dtg_format = self.get_setting('routing', 'dtg_message_format')
        _dtg_format_short = self.get_setting('routing', 'dtg_message_format_short')

        message = self.message_text_to_send_to_ha

        _time = datetime.now().strftime(_dtg_format)
        _short_time = datetime.now().strftime(_dtg_format_short)

        message_package = {"message": message, "zone": self.zone_short_name,
                           "time": _time, "short_time": _short_time}

        if self.image:
            message_package['image'] = self.image.web_url
            message_package['thumbnail'] = self.image.thumbnail_url

        # Send the alert of the full message via MQTT
        out = json.dumps(message_package)
        return out

    def extract_image_data_from_payload(self, payload, camera_name):
        # Pull out useful details from the alert message

        # Local variables:
        base64_str = None
        file_id = None

        _b64_field_name = self.get_setting('routing', 'image_field_name')
        _save_latest_format = self.get_setting('saving', 'save_latest_format')

        # If it doesn't start with a { assume it's a b64 encoded image. Generate paths and get the image data
        if payload and len(payload) > 1000 and payload[0] != "{":
            # A large image payload was received that isn't JSON.  See if it's a bit64 image
            file_id = _save_latest_format.format(camera_name)
            base64_str = payload

        elif payload and 'path' in payload and _b64_field_name in payload:
            # This is likely JSON, try to extract and use it
            try:
                payload_obj = json.loads(payload)
                file_id = payload_obj['path']

                base64_str = get_config_var(_b64_field_name, payload_obj, "")
                self.log("Image {} extracted, size {}".format(file_id, len(base64_str)), level="INFO")
            except ValueError as ex:
                self.log("Received an alert JSON payload: {}".format(ex), level="ERROR")
        else:
            self.log("Invalid JSON or image data received", level="ERROR")

        return base64_str, file_id

    # ==================================

    def get_setting(self, d1, d2):
        # Wrapper to get settings from parent settings object

        if d1 in self._settings:
            if d2 in self._settings[d1]:
                return self._settings[d1][d2]
            else:
                self.log('Error - the setting {} not found in config.{}'.format(d2, d1), level="ERROR")
        else:
            self.log('Error - the setting config.{} not found'.format(d1), level="ERROR")
        return None

    def log(self, message, level="INFO"):
        # Wrapper to main _log object

        if self._log:
            self._log(message, level=level)
        else:
            print("LOG: {}, severity: {}".format(message, level))
