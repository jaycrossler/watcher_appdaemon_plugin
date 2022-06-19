from string_helpers import *


class Zone:

    def __init__(self, id, settings, log=print):
        self.id = id
        self._settings = settings
        self._log = log

        self.description = None
        self.short_name = None
        self.cameras = None
        self.state_entities = None
        self.off_timer = None
        self.alert_objects = None
        self.expected_objects = None

        self.add_zone_info_from_settings()

    def add_zone_info_from_settings(self):
        # Add more details from the settings zone object that matches the name

        for zone in self._settings.zones:
            if self.id.lower() == zone.id.lower():
                self.short_name = get_config_var('short_name', zone, self.name)
                self.description = get_config_var('description', zone, self.name)
                self.cameras = get_config_var('cameras', zone, [])
                self.state_entities = get_config_var('state_entities', zone, [])
                self.off_timer = get_config_var('off_timer', zone, 5)
                self.alert_objects = get_config_var('alert_objects', zone, ['person', 'dog'])
                self.expected_objects = get_config_var('expected_objects', zone, [])
                break

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