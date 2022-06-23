from datetime import datetime, timedelta

from Zones import Zones
from ImageAlertMessage import ImageAlertMessage


class MessageAndZoneHandler:

    def __init__(self,  mqtt_publish, get_entity, settings, log=None):
        self.zones = []
        self.active_events = []
        self.count_of_alert_messages = 0

        self._settings = settings
        self._log = log

        self.mqtt_publish = mqtt_publish
        self.get_entity = get_entity

        self.zones = Zones(settings=self._settings, log=self.log)

    def new_image_alert_message(self, camera_name, payload):
        # Handle messages send from a tool like Blue Iris that contains alert and possibly image data

        self.count_of_alert_messages += 1
        self.log("======== A MQTT message that matched the _image_alert_ topic pattern was received", level="INFO")

        message = ImageAlertMessage(
            camera_name=camera_name,
            payload=payload,
            zones=self.zones,
            log=self.log,
            settings=self._settings,
            message_id=self.count_of_alert_messages
        )
        message.trigger_state_actions(get_entity=self.get_entity)
        message.process_image(mqtt_publish=self.mqtt_publish)
        message.save_message_as_latest(payload=payload)
        message.handle_expected_areas()

        # TODO: Pass in more detailed events to reconstruct timeline
        self.event_happened_in_zone(
            zone_id=message.image_alert.zone_id,
            event=message.image_alert.message_text_to_send_to_ha)

        # Count the number of events in zones
        current = self.current_events_in_zone(zone_id=message.image_alert.zone_id)
        message.send_processed_message(mqtt_publish=self.mqtt_publish, count_of_current=len(current))

    def event_happened_in_zone(self, zone_id, event):
        self.active_events.append({
            'zone_id': zone_id,
            'message': event,
            'message_id': self.count_of_alert_messages,
            'date_time': datetime.now()
        })

    def current_events_in_zone(self, zone_id, since_minutes=10):
        events = []
        for event in self.active_events:
            if event['zone_id'] == zone_id and event['date_time'] > (datetime.now() - timedelta(minutes=since_minutes)):
                events.append(event)

        # Remove old events
        self.active_events = events

        # TODO: Have a dashboard that shows active events per area

        return events

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
