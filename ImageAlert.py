import json
from string_helpers import *
from Imagery import Imagery
from datetime import datetime
import requests
import io


class ImageAlert:

    def __init__(self, camera_name, payload, zones, settings, log=None):
        self.camera_name = camera_name
        self._settings = settings
        self._log = log
        self.zones = zones

        self.image = None
        self.motion_area = None

        self.zone_id = None
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
        self.log("Received payload, extracting")

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

            self.memo = get_config_var('memo', self.payload_obj, "")
            self.analysis = get_config_var('analysis', self.payload_obj, {})

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

            # If face analysis exists, extract out people from those
            _people, _face_analysis_results = self.get_face_contents_from_analysis()

            # Get the zone names from the camera titles
            self.get_zone_name_from_camera_and_zone()

            # Build the alert message from what was in the picture
            _message, _count = self.get_image_contents_from_memo(_people)
            _past_tense = "were" if _count > 1 else "was"

            # Get the event message
            self.message_text_to_send_to_ha = "{} {} seen {}".format(_message, _past_tense, self.zone_name)
            self.count_of_important_things = _count

            # self.log("==JSON: {}".format(self.payload_obj), level="INFO")

        except KeyError as ex:
            self.log("KeyError {} getting camera {} data: {}...".format(ex, camera_name, payload[0:40]), level="ERROR")
        pass

    def get_zone_name_from_camera_and_zone(self):

        matched_zones = self.zones.find_zones_for_camera(self.camera_name, self.motion_area)

        if len(matched_zones) == 1:
            self.zone_id = matched_zones[0].id
            self.zone_short_name = matched_zones[0].short_name
            self.zone_name = matched_zones[0].description
        elif len(matched_zones) == 0:
            self.zone_id = 0
            self.zone_short_name = "not matched"
            self.zone_name = "{} {}".format(self.camera_name, self.motion_area)
        else:
            # more than 1 matched zone
            # TODO: Pick the best zone based on rectangles or sub zones
            self.zone_id = matched_zones[0].id
            self.zone_short_name = matched_zones[0].short_name
            self.zone_name = matched_zones[0].description

    def get_face_contents_from_analysis(self):
        _face_results = extract_face_predictions(self.analysis)
        people = []

        # There were persons found with no analysis and url_face_finder exists, so lookup face matches
        _face_server = self.get_setting('recognition', 'face_server')
        if self.analysis and len(_face_results) == 0 and 'found' in self.analysis[0]\
                and 'predictions' in self.analysis[0]['found'] and self.image and self.image.image\
                and 'url_face_recognizer' in _face_server:

            # Get the boxes where 'person' objects were already found
            person_boxes = []
            for box in self.analysis[0]['found']['predictions']:
                if 'label' in box and box['label'] == 'person' and 'confidence' in box and box['confidence'] > .6:
                    person_boxes.append(box)

            # Convert the image into a set of bytes to send to the recognizer API
            buf = io.BytesIO()
            self.image.image.save(buf, format='JPEG')
            byte_im = buf.getvalue()

            # TODO: Get confidence from settings
            _url = _face_server['url_face_recognizer']
            response = requests.post(_url, files={"image": byte_im}).json()
            if 'status' in response and response['status'] == 404:
                self.log("404 Error accessing face_recognition server {}".format(_url), level="ERROR")
            elif 'predictions' in response:
                for object_f in response["predictions"]:
                    if object_f["confidence"] > .65:
                        people.append(object_f["userid"])
                self.log('Called face recognizer, found: {}'.format(people))
            else:
                self.log("Error accessing face_recognition server", level="ERROR")

        else:
            # Extract face titles from BlueIris results
            for face in _face_results:
                if 'userid' in face:
                    face_title = face['userid']
                    name = substring_before(face_title, "_")
                    if name.lower() != "unknown":
                        # If the name is not 'unknown' add it to the list of people if unique
                        if name.title() not in people:
                            people.append(name.title())

        return people, _face_results

    def get_image_contents_from_memo(self, faces_list):
        memo_from_deepstack = self.memo
        matches = memo_from_deepstack.split(",")

        # TODO: Use items of interest

        people = 0
        dogs = 0
        cars = 0
        _msg = []
        for match in matches:
            m_pieces = match.split(":")
            tag = m_pieces[0]
            # confidence = m_pieces[1]
            if tag == "person":
                people += 1
            elif tag == "dog":
                dogs += 1
            elif tag == "car":
                cars += 1
        #                    _msg = _msg.append["{} ({} confidence)".format(tag, confidence)]

        if people == 1:
            text = "A person"
            if faces_list and len(faces_list):
                text = faces_list[0]
            _msg.append(text)
        elif people > 1:
            text = "{} people".format(people)
            if faces_list and len(faces_list):
                text = ", ".join(faces_list)  # Add face names
            _msg.append(text)

        if dogs == 1:
            _msg.append("A dog")
        elif dogs > 1:
            _msg.append("{} dogs".format(dogs))

        if cars == 1:
            _msg.append("A car")
        elif cars > 1:
            _msg.append("{} cars".format(cars))

        message = ", and ".join(_msg).capitalize()
        return message, people + dogs + cars

    def message_json_to_send_to_ha(self, count_of_current):
        # Prepare a message in JSON format to send to Home Assistant with useful details

        _dtg_format = self.get_setting('routing', 'dtg_message_format')
        _dtg_format_short = self.get_setting('routing', 'dtg_message_format_short')

        message = self.message_text_to_send_to_ha
        if count_of_current > 1:
            message = "{} [{} current]".format(message, count_of_current)

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

    def rectangle_of_interesting_analysis_zones(self):
        min_x = 1000000
        min_y = 1000000
        max_x = 0
        max_y = 0

        width = self.image.image.width if self.image.image and self.image.image.width else 1000
        height = self.image.image.height if self.image.image and self.image.image.height else 1000

        if len(self.analysis) and 'found' in self.analysis[0] and 'predictions' in self.analysis[0]['found']:
            for box in self.analysis[0]['found']['predictions']:
                # TODO: Base these on settings
                if box['label'] in ['person', 'dog', 'car', 'truck'] and box['confidence'] > .6:
                    if box['x_min'] < min_x:
                        min_x = box['x_min']
                    if box['y_min'] < min_y:
                        min_y = box['y_min']
                    if box['x_max'] > max_x:
                        max_x = box['x_max']
                    if box['y_max'] > max_y:
                        max_y = box['y_max']

                    min_x = clip(min_x, 0, max_x)
                    min_y = clip(min_y, 0, max_y)
                    max_x = clip(max_x, min_x, width)
                    max_y = clip(max_y, min_y, height)

            return [min_x, min_y, max_x, max_y]
        else:
            return [0, 0, width, height]

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
