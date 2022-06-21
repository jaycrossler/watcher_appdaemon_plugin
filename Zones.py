from string_helpers import *
from Zone import Zone


class Zones:
    # Holder class for multiple zones.  Helps find the correct zone and track what's happening

    def __init__(self, settings, log=None):
        self._settings = settings
        self._log = log

        self.zone_list = []

        self.set_up_zones()

    def __repr__(self):
        return f'Zones(count:{len(self.zone_list)})'

    def set_up_zones(self):

        self.zone_list = []
        if 'zones' in self._settings:
            for zone_settings in self._settings['zones']:
                new_zone = Zone(zone_settings, log=self.log)
                self.zone_list.append(new_zone)

    def find_zones_for_camera(self, camera, motion_area=None):
        # Find all zones that have the camera and optionally match the motion_area if exists

        found_zones = []

        for zone in self.zone_list:
            for z_cam in zone.cameras:
                z_cam_name = z_cam
                if type(z_cam_name) == dict:
                    z_cam_name = z_cam_name['name']

                if z_cam_name.lower() == camera.lower():
                    if motion_area:
                        # A motion_area was sent in, make sure it matches
                        if type(z_cam) == dict and 'motion_area' in z_cam:
                            if z_cam['motion_area'] == motion_area:
                                found_zones.append(zone)
                            else:
                                continue
                        else:
                            found_zones.append(zone)
                    else:
                        found_zones.append(zone)

        return found_zones

    def get_update_states_for_camera(self, camera, trigger, motion_area=None):
        matched_zones = self.find_zones_for_camera(camera=camera, motion_area=motion_area)

        state_changes = []
        _default_off_timer = self.get_setting('states', 'default_occupancy_off_trigger')

        for zone in matched_zones:
            if zone.state_entities:
                for entity in zone.state_entities:
                    # There is an entity, extract its name and data
                    if type(entity) == dict and 'name' in entity:
                        entity_id = entity['name']
                        delay = get_config_var('delay_off', entity, _default_off_timer)
                    else:
                        entity_id = entity
                        delay = _default_off_timer
                    if type(delay) == int:
                        delay = "{}:00".format(delay)

                    state_changes.append({"entity": entity_id, "state": trigger, "delay": delay})
        return state_changes

    def check_expected_areas_for_matches(self, camera, motion_area=None, image_alert=None):
        matched_zones = self.find_zones_for_camera(camera=camera, motion_area=motion_area)
        _default_off_timer = self.get_setting('states', 'default_occupancy_off_trigger')

        for zone in matched_zones:

            if zone.expected_objects:
                for entity in zone.expected_objects:

                    # There is an expected_object, extract its name and data
                    if type(entity) == dict and 'match' in entity:
                        match_model = get_config_var('match', entity, 'person')
                        match_type = get_config_var('type', entity, 'exists')
                        match_entity = get_config_var('state_entity', entity, None)
                        match_color = get_config_var('color', entity, None)
                        match_delay_off = get_config_var('delay_off', entity, _default_off_timer)
                    else:
                        match_model = entity
                        match_type = 'exists'
                        match_entity = None
                        match_color = None
                        match_delay_off = _default_off_timer
                    if type(match_delay_off) == int:
                        match_delay_off = "{}:00".format(match_delay_off)

                #if self.exists_in_image()
                # TODO: Finish

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
