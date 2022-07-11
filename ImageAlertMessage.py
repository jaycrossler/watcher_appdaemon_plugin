from ImageAlert import ImageAlert
import posixpath


class ImageAlertMessage:

    def __init__(self, camera_name, payload, zones, settings, message_id, log=None):
        self.camera_name = camera_name
        self._settings = settings
        self._log = log
        self.zones = zones
        self.active_events = []
        self.message_id = message_id

        self.image_alert = ImageAlert(
                camera_name=camera_name,
                payload=payload,
                zones=self.zones,
                settings=self._settings,
                log=self.log)

    def trigger_state_actions(self, get_entity):
        # Trigger any HA actions based on the message contents
        if self.image_alert.trigger and self.image_alert.trigger.lower() in ["on", "off"]:
            # If there are any state changes to HA objects, do those now
            state_updates = self.zones.get_update_states_for_camera(
                camera=self.image_alert.camera_name,
                trigger=self.image_alert.trigger,
                motion_area=self.image_alert.motion_area)

            # TODO: Handle Delay here
            for s in state_updates:
                entity = get_entity(s['entity'])
                entity.set_state(state=s['state'])
                self.log("Set State {} to {}".format(s['entity'], s['state']))

    def process_image(self, mqtt_publish):

        # If the message had an image, create an image object and save it to disk
        image = self.image_alert.image
        if image:
            _topic_latest = self.get_setting('routing', 'mqtt_publish_to_for_latest_image')

            # TODO: Move this logic into the IA class
            interesting_rect = self.image_alert.rectangle_of_interesting_analysis_zones()

            # Save images as necessary
            image.save_full_sized(snip_rectangle=interesting_rect)
            image.save_thumbnail(snip_rectangle=interesting_rect)
            image.save_full_sized(save_as_latest=True, snip_rectangle=interesting_rect)

            # Post a message just of the URL to the 'latest' topic
            if image.web_url and _topic_latest:
                mqtt_publish(_topic_latest, image.web_url)
                self.log("Published latest alert to {} - {}".format(_topic_latest, image.web_url), level="INFO")

            # Remove old images to save disk space
            image.clean_image_folders()

    def save_message_as_latest(self, payload):
        # Save out the latest message in JSON format for better testing
        file_to_write_to = self.get_setting('saving', 'save_latest_json_to_file')
        if file_to_write_to:
            _save_loc = self.get_setting('saving', 'path_to_save_images')
            file_loc = posixpath.join(_save_loc, file_to_write_to)
            with open(file_loc, 'w') as out_file:
                out_file.write(payload)
                # json.dump(payload, out_file, sort_keys=True, indent=4, ensure_ascii=False)
                self.log("Saved previous json message to {}".format(file_loc), level="INFO")

    def handle_expected_areas(self):

        # TODO: Handle expected objects and have it return messaging if expectations changed
        self.zones.check_expected_areas_for_matches(
            camera=self.camera_name,
            motion_area=self.image_alert.motion_area,
            image_alert=self.image_alert
        )

    # =========================================

    def log(self, message, level="INFO"):
        # Wrapper to main _log object

        if self._log:
            self._log(message, level=level)
        else:
            print("{}: {} [{}]".format(self.message_id, message, level))

    def get_setting(self, d1, d2):
        if d1 in self._settings:
            if d2 in self._settings[d1]:
                return self._settings[d1][d2]
            else:
                self.log('[ERROR] the setting {} not found in config.{}'.format(d2, d1), level="ERROR")
        else:
            self.log('[ERROR] the setting config.{} not found'.format(d1), level="ERROR")
        return None
