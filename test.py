import json

import requests
from string_helpers import *
from MessageRouterConfiguration import MessageRouterConfiguration
import random

from Zones import Zones
from MessageAndZoneHandler import MessageAndZoneHandler
# from ImageAlert import ImageAlert
# from ImageAlertMessage import ImageAlertMessage

# import json
# import io
# import time

VERBOSE = False


def log(message, level="LOG"):
    if VERBOSE or level in ["ERROR"]:
        print(message)


class TestCommands:
    log = log

    _settings = {}
    settings = {}

    def initialize(self):
        # self.apiUrl = "http://homeassistant.local:8123/api/logbook"
        self.log("===========Test Module Loaded========")

        self.set_config_variables()

    def set_config_variables(self):
        # Load configuration variables
        _config = {
            'config_file': 'config.yaml'
        }
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
        self.settings = _merged_config


def fetch(self, path):
    TOKEN = ".."
    headers = {
        "Authorization": "Bearer {}".format(TOKEN),
        "content-type": "application/json"
    }
    res = requests.get(path, headers=headers)
    return res.text # json.loads(res.text)


def mqtt_publish(topic, message):
    print("MOCK MQTT: {} to {}".format(message, topic))


class Get_entity_wrapper:
    name = None

    def __init__(self, name):
        self.name = name

    def set_state(self, state):
        if VERBOSE:
            print("SET STATE FOR {} to {}".format(self.name, state))


def get_entity(name):
    return Get_entity_wrapper(name)


def mod_payload_for_testing(payload, person_pct, people, x=1000, y=1000):
    payload_mod = json.loads(payload)

    people_text = 'person:{}%'.format(person_pct)
    if people and type(people) == list and len(people):
        people_arr = []

        # Add in predictions to face a face recognizer payload
        pred = []
        for p in people:
            pred.append({'confidence': random.randint(person_pct-30, 99), 'label': p, 'userid': p})
        payload_mod['analysis'].append({"api": "faces", 'found': {'success': True, 'predictions': pred}})

        # Build the "person:" memo text
        for i in range(len(people)):
            people_arr.append('person:{}%'.format(random.randint(person_pct-30, 99)))
        people_text = ",".join(people_arr)

        if len(payload_mod['analysis']) and 'found' in payload_mod['analysis'][0] and 'predictions' in payload_mod['analysis'][0]['found']:
            person = {'label': 'person', 'confidence': 0.7067128, 'y_min': 1175, 'x_min': 1223, 'y_max': 2062, 'x_max': 1730}

            # Get the person value if exists, delete it
            for i, box in enumerate(payload_mod['analysis'][0]['found']['predictions']):
                if box['label'] == 'person':
                    person = box
                    del payload_mod['analysis'][0]['found']['predictions'][i]

            # Add more simulated people
            for i in range(len(people)):
                new_person = person
                new_person['confidence'] = random.randint(person_pct-30, 99)/100
                new_person['x_min'] += random.randint(-x, x)
                new_person['y_min'] += random.randint(-y, y)
                new_person['x_max'] += random.randint(-x, x)
                new_person['y_max'] += random.randint(-y, y)
                payload_mod['analysis'][0]['found']['predictions'].append(new_person)


    payload_mod['memo'] = people_text

    return json.dumps(payload_mod)


def write_array_to_test_timeline(output_items, output_groups, css_groups, earliest, latest):
    filename_fm = "timeline/test_source.html"
    filename_to = "timeline/test.html"
    if os.path.exists(filename_fm):
        with open(filename_fm, 'r') as source_file:
            source_file_text = source_file.read()
            new_text = source_file_text.replace("INSERT_ITEM_ARRAY_HERE", str(output_items))
            new_text = new_text.replace("INSERT_GROUP_ARRAY_HERE", str(output_groups))
            new_text = new_text.replace("INSERT_GROUP_CSS_HERE", str(css_groups))

            options = {"start": earliest, "end": latest, "tooltip": {"followMouse": True, "overflowMethod": 'cap'}}
            new_text = new_text.replace("INSERT_OPTIONS_SETTINGS_HERE", json.dumps(options))

            with open(filename_to, 'w') as to_file:
                to_file.write(new_text)


def what_zone_is_point_from_camera_in(camera, point, zone_list):
    for zone in zone_list:
        if 'cameras' in zone:
            for cam in zone['cameras']:
                if cam['name'] == camera and 'polygons' in cam:
                    for poly in cam['polygons']:
                        if point_in_polygon(poly, point):
                            return zone['description'] if 'description' in zone else zone['id']
    return None


if __name__ == '__main__':
    TC = TestCommands()
    TC.initialize()
    TC.settings['saving']['path_to_save_images'] = "test/"
    TC.settings['saving']['web_path_to_images'] = "../test/"
    TC.settings['saving']['thumbnails_subdir'] = "thumbnails/"
    TC.settings['routing']['mqtt_publish_to_for_latest_image'] = None
    zones = Zones(settings=TC.settings)

    with open('test/test_msg.json') as f:
        test_msg_content = f.readlines()

    payload_driveway = test_msg_content[0]

    # Build the major "handler" that routes messages into alert groups
    message_and_zone_handler = MessageAndZoneHandler(
        mqtt_publish=mqtt_publish,
        get_entity=get_entity,
        settings=TC.settings,
        log=log
    )

    # Load payload as a message, then change variables and load a few more times for testing
    message_and_zone_handler.new_image_alert_message(
        camera_name='annke1hd', payload=payload_driveway, seconds_offset=-60*50)
    message_and_zone_handler.new_image_alert_message(
        camera_name='annke1hd', payload=payload_driveway, seconds_offset=-60*20)
    payload = mod_payload_for_testing(payload_driveway, person_pct=60, people=['jay'], x=50, y=50)
    message_and_zone_handler.new_image_alert_message(
        camera_name='annke1hd', payload=payload, seconds_offset=-60*10)
    payload = mod_payload_for_testing(payload_driveway, person_pct=60, people=['jay', 'jackie'], x=100, y=100)
    message_and_zone_handler.new_image_alert_message(
        camera_name='annke1hd', payload=payload, seconds_offset=-60*6)
    payload = mod_payload_for_testing(payload_driveway, person_pct=80, people=['jay', 'jackie', 'julian'], x=200, y=200)
    message_and_zone_handler.new_image_alert_message(
        camera_name='annke1hd', payload=payload, seconds_offset=-60*2)
    message_and_zone_handler.new_image_alert_message(
        camera_name='annke1hd', payload=payload_driveway)

    # Build deck messages to test
    with open('test/test_msg_deck.json') as f:
        test_msg_content = f.readlines()
    payload_deck = test_msg_content[0]

    message_and_zone_handler.new_image_alert_message(
        camera_name='annke4hd', payload=payload_deck, seconds_offset=-60*5)

    payload = mod_payload_for_testing(
        payload_deck, person_pct=60, people=['jay', 'jackie'], x=200, y=200)
    message_and_zone_handler.new_image_alert_message(
        camera_name='annke4hd', payload=payload, seconds_offset=-60*4.1)

    payload = mod_payload_for_testing(
        payload_deck, person_pct=70, people=['jackie'], x=200, y=200)
    message_and_zone_handler.new_image_alert_message(
        camera_name='annke4hd', payload=payload, seconds_offset=-60*3.5)

    payload = mod_payload_for_testing(
        payload_deck, person_pct=70, people=['jackie'], x=200, y=200)
    message_and_zone_handler.new_image_alert_message(
        camera_name='annke4hd', payload=payload, seconds_offset=-60*2.1)

    payload = mod_payload_for_testing(
        payload_deck, person_pct=80, people=['jackie'], x=120, y=120)
    message_and_zone_handler.new_image_alert_message(
        camera_name='annke4hd', payload=payload, seconds_offset=-60*1.1)

    message_and_zone_handler.new_image_alert_message(
        camera_name='annke4hd', payload=payload_deck)

    # Build the test timeline file
    timeline_json_items, earliest, latest = message_and_zone_handler.alert_groups.timeline_json_items()
    timeline_json_groups = message_and_zone_handler.alert_groups.timeline_json_groups(show_all=False)
    timeline_css_groups = message_and_zone_handler.alert_groups.timeline_css_groups()
    write_array_to_test_timeline(timeline_json_items, timeline_json_groups, timeline_css_groups, earliest, latest)


    # imagery = iam.image_alert.image
    # analysis = iam.image_alert.analysis
    # print(imagery.image.size)
    #
    # interesting_rect = iam.image_alert.rectangle_of_interesting_analysis_zones()
    # piece = imagery.get_piece_of_image(interesting_rect, padding=10)
    # print(piece.size)

    # buf = io.BytesIO()
    # piece.save(buf, format='JPEG')
    # byte_im = buf.getvalue()

    # response = requests.post("http://daedelus.lan:5000/v1/vision/detection", files={"image": byte_im}).json()
    # for object in response["predictions"]:
    #     print("{} - {}%".format(object["label"], round(object["confidence"]*100, 1)))
    # print(response)
    #
    # response = requests.post("http://daedelus.lan:5000/v1/vision/face", files={"image": byte_im}).json()
    # print('FACE finder: {}'.format(response))
    # for object in response["predictions"]:
    #     face_boxes = [object["x_min"], object["y_min"], object["x_max"], object["y_max"]]
    #     print("{} - {}%".format(face_boxes, round(object["confidence"]*100, 1)))
    #
    #     face = piece.copy().crop((face_boxes[0], face_boxes[1], face_boxes[2], face_boxes[3]))
    #     face.save(buf, format='JPEG')
    #     byte_im = buf.getvalue()
    #
    #     response = requests.post("http://daedelus.lan:5000/v1/vision/face/recognize", files={"image": byte_im}).json()
    #     print('FACE recognizer: {}'.format(response))
    #     for object_f in response["predictions"]:
    #         print("{} - {}%".format(object_f["userid"], round(object_f["confidence"]*100, 1)))

    # piece.save('test/test_piece.jpg')

    # image_alert = ImageAlert('annke1hd', img_t, TC.settings)
    # image = image_alert.image

    # img_t = open('test_msg.json')
    # img_data = json.load(img_t)
    # img_text = img_data['image_b64']
    # imagery = Imagery('test.jpg', img_text, 'virtual_cam', TC.settings)
    # imagery.save_full_sized()
    # imagery.save_thumbnail()
    # imagery.save_full_sized(save_as_latest=True)

    # piece = imagery.get_piece_of_image([50,50,200,200], padding=10)
    # piece.save('test_piece.jpg')

    # cam = 'eufy1'
    # cam_match = zones.find_zones_for_camera(cam)
    # print('{}: {}'.format(cam, cam_match))
    # zones.update_state_for_camera(camera=cam, trigger='on')
    #
    # cam = 'reolink6'
    # cam_match = zones.find_zones_for_camera(cam)
    # print('{}: {}'.format(cam, cam_match))
    # zones.update_state_for_camera(camera=cam, trigger='on')
    #
    # cam = 'reolink6'
    # mot = 'A'
    # cam_match = zones.find_zones_for_camera('reolink6', mot)
    # print('{}: {} - motion area {}'.format(cam, cam_match, mot))
    # zones.update_state_for_camera(camera=cam, trigger='on', motion_area=mot)


'''
To paste into terminal:

from Zones import Zones
from test import TestCommands
TC = TestCommands()
TC.initialize()
zones = Zones(settings=TC._settings)
cam_match = zones.find_zones_for_camera('eufy1')
print('efy1: {}'.format(cam_match))

'''