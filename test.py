import json

import requests
from string_helpers import *
from MessageRouterConfiguration import MessageRouterConfiguration
from datetime import datetime

from Zones import Zones
from MessageAndZoneHandler import MessageAndZoneHandler
# from ImageAlert import ImageAlert
# from ImageAlertMessage import ImageAlertMessage

# import json
# import io
# import time


class TestCommands:
    def log(self, message, severity="LOG"):
        print(message)

    _settings = {}
    settings = {}

    def initialize(self):
        # self.apiUrl = "http://homeassistant.local:8123/api/logbook"
        now = datetime.now()
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
        print("SET STATE FOR {} to {}".format(self.name, state))


def get_entity(name):
    return Get_entity_wrapper(name)


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
    TC.settings['saving']['thumbnails_subdir'] = "thumbnails/"
    zones = Zones(settings=TC.settings)

    with open('test/test_msg.json') as f:
        test_msg_content = f.readlines()

    payload = test_msg_content[0]

    message_and_zone_handler = MessageAndZoneHandler(
        mqtt_publish=mqtt_publish,
        get_entity=get_entity,
        settings=TC.settings
    )

    f = open('test/extracted_zones.json')
    test_zones = json.load(f)

    print(what_zone_is_point_from_camera_in('annke1hd', [.5, .5], test_zones))
    print(what_zone_is_point_from_camera_in('annke1hd', [.1, .1], test_zones))
    print(what_zone_is_point_from_camera_in('annke1hd', [.2, .8], test_zones))
    print(what_zone_is_point_from_camera_in('annke1hd', [.7, .7], test_zones))
    print(what_zone_is_point_from_camera_in('annke2hd', [.5, .5], test_zones))

    # message_and_zone_handler.new_image_alert_message(camera_name='annke1hd', payload=payload)
    #
    # message_and_zone_handler.new_image_alert_message(camera_name='annke1hd', payload=payload)
    #
    # # Also play back last message
    # with open('test/test_msg_deck.json') as f:
    #     test_msg_content = f.readlines()
    # payload = test_msg_content[0]
    #
    # message_and_zone_handler.new_image_alert_message(camera_name='annke4hd', payload=payload)
    #
    # message_and_zone_handler.new_image_alert_message(camera_name='annke4hd', payload=payload)

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