from ImageAlert import ImageAlert
import posixpath


class ImageAlertMessage:

    def __init__(self, camera_name, payload, zones, mqtt_publish, get_entity, settings, log=None):
        self.camera_name = camera_name
        self._settings = settings
        self._log = log
        self.zones = zones
        self.mqtt_publish = mqtt_publish
        self.get_entity = get_entity

        self.image_alert = self.handle_image_alert_message(camera_name=camera_name, payload=payload)

    def handle_image_alert_message(self, camera_name, payload):
        # Handle messages send from a tool like Blue Iris that contains alert and possibly image data

        try:
            self.log("A MQTT message that matched the _image_alert_ topic pattern was received", level="INFO")

            _topic_latest = self.get_setting('routing', 'mqtt_publish_to_for_latest_image')
            _topic_ha_alert = self.get_setting('routing', 'mqtt_publish_to_topic')

            # Create the main ImageAlert object
            image_alert = ImageAlert(camera_name, payload, self._settings, self.log)

            # Trigger any HA actions based on the message contents
            if image_alert.trigger and image_alert.trigger.lower() in ["on", "off"]:
                # If there are any state changes to HA objects, do those now
                state_updates = self.zones.get_update_states_for_camera(
                    camera=image_alert.camera_name,
                    trigger=image_alert.trigger,
                    motion_area=image_alert.motion_area)

                # TODO: Handle Delay here
                for s in state_updates:
                    entity = self.get_entity(s['entity'])
                    entity.set_state(state=s['state'])

            else:
                self.log("Unknown trigger state {} - {} - {}".format(
                    image_alert.camera_name, image_alert.motion_area, image_alert.trigger), level="INFO")

            # If the message had an image, create an image object and save it to disk
            if image_alert.image:
                image = image_alert.image

                # Save images as necessary
                image.save_full_sized()
                image.save_thumbnail()
                image.save_full_sized(save_as_latest=True)

                # Post a message just of the URL to the 'latest' topic
                if image.web_url:
                    self.mqtt_publish(_topic_latest, image.web_url)
                    self.log("Published latest alert to {} - {}".format(_topic_latest, image.web_url), level="INFO")

                # Remove old images to save disk space
                image.clean_image_folders()

                # Save out the latest message in JSON format for better testing
                file_to_write_to = self.get_setting('saving', 'save_latest_json_to_file')
                if file_to_write_to:
                    _save_loc = self.get_setting('saving', 'path_to_save_images')
                    file_loc = posixpath.join(_save_loc, file_to_write_to)
                    with open(file_loc, 'w') as out_file:
                        out_file.write(payload)
                        # json.dump(payload, out_file, sort_keys=True, indent=4, ensure_ascii=False)
                        self.log("Saved previous json message to {}".format(file_loc), level="INFO")

            # TODO: Handle expected objects and have it return messaging if expectations changed
            self.zones.check_expected_areas_for_matches(
                camera=camera_name,
                motion_area=image_alert.motion_area,
                image_alert=image_alert
            )

            # Send the message if it's new
            # TODO: Incorporate priority and new zones text
            _message_text = image_alert.message_text_to_send_to_ha
            if image_alert.count_of_important_things > 0:
                # Send a JSON package of the image alert for HA to use
                message = image_alert.message_json_to_send_to_ha()
                self.mqtt_publish(_topic_ha_alert, message)

                # Save that it was the last one sent to reduce duplicates
                self.log("Published to {} - {}".format(_topic_ha_alert, message), level="INFO")
            else:
                self.log("Something {} - but empty so not publishing".format(_message_text), level="DEBUG")

            return image_alert
        except KeyError as ex:
            self.log("KeyError problem in handling image message: {}".format(ex), level="ERROR")
            return None

    def log(self, message, level="INFO"):
        # Wrapper to main _log object

        if self._log:
            self._log(message, level=level)
        else:
            print("LOG: {}, severity: {}".format(message, level))

    def get_setting(self, d1, d2):
        if d1 in self._settings:
            if d2 in self._settings[d1]:
                return self._settings[d1][d2]
            else:
                self.log('[ERROR] the setting {} not found in config.{}'.format(d2, d1), level="ERROR")
        else:
            self.log('[ERROR] the setting config.{} not found'.format(d1), level="ERROR")
        return None
