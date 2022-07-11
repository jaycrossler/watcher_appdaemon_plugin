from string_helpers import *


class Zone:

    def __init__(self, zone_settings, log=None):
        self._settings = zone_settings
        self._log = log

        self.id = id
        self.description = None
        self.short_name = None
        self.cameras = None
        self.state_entities = None
        self.off_timer = None
        self.alert_objects = None
        self.expected_objects = None
        self.alert_group = None

        self.add_zone_info_from_settings(zone_settings)

    def __str__(self):
        return f'Zone({self.id}:{self.description} - Cameras:{self.cameras})'

    def __repr__(self):
        return f'Zone({self.id}:{self.description} - Cameras:{self.cameras})'

    def add_zone_info_from_settings(self, zone_settings):
        # Add more details from the settings zone object that matches the name

        self.id = get_config_var('id', zone_settings, 'unknown')
        self.short_name = get_config_var('short_name', zone_settings, self.id)
        self.alert_group = get_config_var('alert_group', zone_settings, self.id)
        self.description = get_config_var('description', zone_settings, self.id)
        self.cameras = get_config_var('cameras', zone_settings, [])
        self.state_entities = get_config_var('state_entities', zone_settings, [])
        self.off_timer = get_config_var('off_timer', zone_settings, 5)
        self.alert_objects = get_config_var('alert_objects', zone_settings, ['person:.7', 'dog:.5'])
        self.expected_objects = get_config_var('expected_objects', zone_settings, [])

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
