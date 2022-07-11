from Zones import Zones
from AlertGroups import AlertGroups
from ImageAlertMessage import ImageAlertMessage
import json

# TODO: Have a dashboard that shows active events per area
# TODO: Have an API to get updates of when event info changes


class MessageAndZoneHandler:

    def __init__(self,  mqtt_publish, get_entity, settings, log=None):
        self.zones = []
        self.count_of_alert_messages = 0

        self._settings = settings
        self._log = log

        self.mqtt_publish = mqtt_publish
        self.get_entity = get_entity

        self.zones = Zones(settings=self._settings, log=self.log)
        self.alert_groups = AlertGroups(zones=self.zones, settings=self._settings, log=self.log)

    def new_image_alert_message(self, camera_name, payload, seconds_offset=0):
        # Handle messages send from a tool like Blue Iris that contains alert and possibly image data

        self.count_of_alert_messages += 1
        self.log("======== A MQTT message that matched the _image_alert_ topic pattern was received", level="INFO")

        # Build the message handler that parses inputs from the NVR, then dies actions and interprets contents
        message = ImageAlertMessage(
            camera_name=camera_name,
            payload=payload,
            zones=self.zones,
            log=self.log,
            settings=self._settings,
            message_id=self.count_of_alert_messages
        )

        # Handle the parts of the message
        message.trigger_state_actions(get_entity=self.get_entity)
        message.process_image(mqtt_publish=self.mqtt_publish)
        message.save_message_as_latest(payload=payload)
        message.handle_expected_areas()

        # Build Alert Groups and send a message if important enough to send
        alert_group = self.alert_groups.group_from_zone_id(zone_id=message.image_alert.zone_id)
        if alert_group:
            message_package = alert_group.message_received_for_zone(
                message=message,
                zone_id=message.image_alert.zone_id,
                seconds_offset=seconds_offset
            )
            if message_package:
                self.send_message_package(message_package)
        else:
            self.log('A zone was not found when trying to build alert_group messages', level="ERROR")

    def send_message_package(self, message_package):
        # Turn the message package into text to send
        out = json.dumps(message_package)

        # Send the alert of the full message via MQTT
        _topic_ha_alert = self.get_setting('routing', 'mqtt_publish_to_topic')
        self.mqtt_publish(_topic_ha_alert, out)
        self.log("Published to {} - {}".format(_topic_ha_alert, message_package), level="INFO")

    # =========================================

    def log(self, message, level="INFO"):
        # Wrapper to main _log object

        message = "{}: {}".format(self.count_of_alert_messages, message)

        if self._log:
            self._log(message, level=level)
        else:
            print("{}: {} [{}]".format(self.count_of_alert_messages, message, level))

    def get_setting(self, d1, d2):
        if d1 in self._settings:
            if d2 in self._settings[d1]:
                return self._settings[d1][d2]
            else:
                self.log('[ERROR] the setting {} not found in config.{}'.format(d2, d1), level="ERROR")
        else:
            self.log('[ERROR] the setting config.{} not found'.format(d1), level="ERROR")
        return None
