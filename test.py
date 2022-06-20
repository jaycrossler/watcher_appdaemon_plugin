import requests
from string_helpers import *
from MessageRouterConfiguration import MessageRouterConfiguration
from datetime import datetime
from Zones import Zones


# import appdaemon.plugins.hass.hassapi as hass
# class TestCommands(hass.Hass):
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


if __name__ == '__main__':
    TC = TestCommands()
    TC.initialize()
    zones = Zones(settings=TC.settings)

    cam = 'eufy1'
    cam_match = zones.find_zones_for_camera(cam)
    print('{}: {}'.format(cam, cam_match))
    zones.update_state_for_camera(camera=cam, trigger='on')

    cam = 'reolink6'
    cam_match = zones.find_zones_for_camera(cam)
    print('{}: {}'.format(cam, cam_match))
    zones.update_state_for_camera(camera=cam, trigger='on')

    cam = 'reolink6'
    mot = 'A'
    cam_match = zones.find_zones_for_camera('reolink6', mot)
    print('{}: {} - motion area {}'.format(cam, cam_match, mot))
    zones.update_state_for_camera(camera=cam, trigger='on', motion_area=mot)


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