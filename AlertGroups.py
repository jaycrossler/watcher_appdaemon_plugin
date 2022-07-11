from AlertGroup import AlertGroup
import json
from string_helpers import *


class AlertGroups:
    # Holder class for multiple Alert Groups (based on zones).
    # Helps find the correct zone and track what's happening

    def __init__(self, zones, settings, log=None):
        self._log = log
        self._settings = settings

        self.zones = zones
        self.alert_group_list = []

        self.set_up_alert_groups()

    def __repr__(self):
        return f'AlertGroups(count:{len(self.alert_group_list)})'

    def set_up_alert_groups(self):
        # Group Zones into AlertGroups

        self.alert_group_list = []

        for zone in self.zones.zone_list:
            alert_group_exists = False
            for ag in self.alert_group_list:
                if ag.name == zone.alert_group:
                    alert_group_exists = True
                    ag.add_zone(zone)

            if not alert_group_exists:
                new_ag = AlertGroup(name=zone.alert_group,
                                    event_group_id=len(self.alert_group_list)+1,
                                    settings=self._settings,
                                    log=self.log)
                new_ag.add_zone(zone)
                self.alert_group_list.append(new_ag)

    def group_from_zone_id(self, zone_id):
        for ag in self.alert_group_list:
            for zone in ag.zones:
                if zone.id == zone_id:
                    return ag
        return None

    def timeline_css_groups(self):
        output = ''
        for ag in self.alert_group_list:
            # Border for active events
            output += '      .vis-item.{} {{ border-color: {}; color: {}; }}\n'.format(
                ag.group_html_name, ag.css_color, ag.css_text_color)

            # Background for alert group zones
            output += '      .vis-label.vis-group-level-0.{} {{ background-color: {}; color: {}; }}\n'.format(
                ag.group_html_name, ag.css_color, ag.css_text_color)

            if len(ag.events):
                # Background for event groups
                output += '      .vis-item.vis-background.bg{} {{ background-color: {}; opacity:0.5; }}\n'.format(
                    str(ag.event_group_id), ag.css_color)

            for old in ag.old_events:
                # Background for old event groups
                cid = old['event_group_id'].replace(".", "-")
                output += '      .vis-item.vis-background.bg{} {{ background-color: {}; opacity:0.5; }}\n'.format(
                    cid, old['css_color'])

        return output

    def timeline_json_groups(self, show_all=False):
        output = []
        for ag in self.alert_group_list:
            group = {'id': ag.event_group_id,
                     'content': ag.name.title(),
                     'visible': True if show_all else len(ag.events) > 0,
                     'className': ag.group_html_name}

            output.append(group)

        return json.dumps(output, indent=2)

    def timeline_json_items(self, include_old=True):
        output = []
        for ag in self.alert_group_list:
            # Clean up any old events
            ag.move_any_old_events_to_old()

            # Get all current events in json format
            output += ag.events_as_json(include_background=True)
            if include_old:
                output += ag.old_events_as_json(include_background=True)

        earliest, latest = get_time_ranges(output, self.get_setting('routing', 'dtg_message_format'))

        return json.dumps(output, indent=2), earliest, latest

    # ==================================

    def get_setting(self, d1, d2):
        if d1 in self._settings:
            if d2 in self._settings[d1]:
                return self._settings[d1][d2]
            else:
                self.log('[ERROR] the setting {} not found in config.{}'.format(d2, d1), level="ERROR")
        else:
            self.log('[ERROR] the setting config.{} not found'.format(d1), level="ERROR")
        return None

    def log(self, message, level="INFO"):
        # Wrapper to main _log object

        if self._log:
            self._log(message, level=level)
        else:
            print("LOG: {}, severity: {}".format(message, level))
