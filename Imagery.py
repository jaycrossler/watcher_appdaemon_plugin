import posixpath
import base64
import io
from PIL import Image, UnidentifiedImageError
import os
import time


class Imagery:
    # Manage images

    def __init__(self, file_id, payload, camera, settings, log=print):
        self.file_id = file_id
        self.payload = payload
        self.camera = camera
        self._settings = settings
        self.binary = base64.b64decode(str(payload))
        self._log = log
        self.web_url = None
        self.thumbnail_url = None

        # except:
        #     # TODO: Add error checking
        #     self.binary = None

    def save_thumbnail(self):
        # Save a thumbnail of the image
        _save_loc = self.get_setting('saving', 'path_to_save_images')
        _thumbnails_subdir = self.get_setting('saving', 'thumbnails_subdir')
        _thumbnail_path = posixpath.join(_save_loc, _thumbnails_subdir, self.file_id)
        _thumbnails_size = self.get_setting('saving', 'thumbnail_max_size')
        _web_path_to_images = self.get_setting('saving', 'web_path_to_images')

        try:
            # Also create a thumbnail
            img = Image.open(io.BytesIO(self.binary))
            img.thumbnail((_thumbnails_size, _thumbnails_size))
            img.save(fp=_thumbnail_path)
            self.thumbnail_url = posixpath.join(_web_path_to_images, _thumbnails_subdir, self.file_id)

            self.log("Saved a thumbnail to {}".format(_thumbnail_path), level="INFO")

        except FileNotFoundError as ex:
            self.log("Error {} could not save file {]".format(ex, _thumbnail_path), level="ERROR")
        except UnidentifiedImageError as ex:
            self.log("Error {} PIL could not import the included image".format(ex), level="ERROR")
        except ValueError as ex:
            self.log("Error {} saving smaller image {} - {}".format(ex, self.file_id, len(self.binary)), level="ERROR")

    def save_as_latest(self):
        # Save the image as the "latest" image - # TODO: Combine with other save methods
        _save_to = self.get_setting('saving', 'path_to_save_images')
        _save_latest_format = self.get_setting('saving', 'save_latest_format')
        _max_size = int(self.get_setting('saving', 'thumbnail_max_size'))

        latest_path = posixpath.join(_save_to, _save_latest_format.format("alert.jpg"))
        _cam = self.camera
        _file = self.file_id
        _size = len(self.payload) if self.payload else 0

        try:
            with open(latest_path, "wb") as fh:
                fh.write(base64.b64decode(str(self.payload)))
                # fh.write(self.binary) # TODO - use this instead
                self.log("Saved latest image from [{}] to {} - size {}".format(_cam, _file, _size), level="INFO")
        except IOError as ex:
            self.log("Error {} Could not save image: {} to {} - size {}".format(ex, _cam, _file, _size), level="ERROR")

    def save_full_sized(self):
        # Save the image file
        _save_to = self.get_setting('saving', 'path_to_save_images')
        _cam = self.camera
        _file = self.file_id
        _size = len(self.payload) if self.payload else 0
        _web_path_to_images = self.get_setting('saving', 'web_path_to_images')

        path = posixpath.join(_save_to, self.file_id)

        try:
            with open(path, "wb") as fh:
                fh.write(base64.b64decode(str(self.payload)))
                # fh.write(self.binary) # TODO - use this instead
                self.log("Saved an image from [{}] to {} - size {}".format(_cam, _file, _size), level="INFO")
                self.web_url = posixpath.join(_web_path_to_images, self.file_id)

        except TypeError as ex:
            self.log("Error {} Could not save image: [{}] to {} - {}".format(ex, _cam, _file, _size), level="ERROR")

    def clean_image_folders(self):
        # Delete old files in image directories
        _days_to_keep = self.get_setting('saving', 'days_to_keep_images')
        if _days_to_keep and int(_days_to_keep) > 0:
            _save_loc = self.get_setting('saving', 'path_to_save_images')
            _thumbnails_subdir = self.get_setting('saving', 'thumbnails_subdir')
            _thumbnail_path = posixpath.join(_save_loc, _thumbnails_subdir)

            self.remove_files_older_than(_save_loc, _days_to_keep)
            self.remove_files_older_than(_thumbnail_path, _days_to_keep)

    # ---------------------------------------------

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

    def remove_files_older_than(self, dir_path, limit_days):
        # Delete files that are older than n days
        files_removed = 0

        threshold = time.time() - limit_days * 86400
        entries = os.listdir(dir_path)
        for file in entries:
            file_pointer = os.path.join(dir_path, file)
            creation_time = os.stat(file_pointer).st_ctime
            if creation_time < threshold:
                os.remove(file_pointer)
                files_removed += 1
        if files_removed > 0:
            self.log("Removed {} old files from {}".format(files_removed, dir_path), level="INFO")

    def log(self, message, level="INFO"):
        # Wrapper to main _log object

        if self._log:
            self._log(message, level=level)
