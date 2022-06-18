import posixpath
import base64
import io
from PIL import Image, UnidentifiedImageError
import os
import time


class Imagery:
    # Manage images

    def __init__(self, file_id, payload, camera, settings):
        self.file_id = file_id
        self.payload = payload
        self.camera = camera
        self._settings = settings
        self.binary = base64.b64decode(str(payload))

        # except:
        #     # TODO: Add error checking
        #     self.binary = None

    def save_thumbnail(self):
        _save_loc = self.get_setting('saving', 'path_to_save_images')
        _thumbnails_subdir = self.get_setting('saving', 'thumbnails_subdir')
        _thumbnail_path = posixpath.join(_save_loc, _thumbnails_subdir, self.file_id)
        _thumbnails_size = self.get_setting('saving', 'thumbnail_max_size')

        message = None
        error = None
        try:
            # Also create a thumbnail
            # self.log("...Saving a thumbnail to {}".format(path_thumbnail))
            img = Image.open(io.BytesIO(self.binary))
            img.thumbnail((_thumbnails_size, _thumbnails_size))
            img.save(fp=_thumbnail_path)
            # self.log("...Saved a thumbnail also to {}".format(path_thumbnail))

        except FileNotFoundError as ex:
            error = "[ERROR {}] could not save file {]".format(ex, _thumbnail_path)
        except UnidentifiedImageError as ex:
            error = "[ERROR {}] PIL could not import the included image".format(ex)
        except ValueError as ex:
            error = "[ERROR {}] on saving a smaller image {}, size {}".format(ex, self.file_id, len(self.binary))

        return message, error

    def save_as_latest(self):
        _save_to = self.get_setting('saving', 'path_to_save_images')
        _save_latest_format = self.get_setting('saving', 'save_latest_format')
        _max_size = int(self.get_setting('saving', 'thumbnail_max_size'))

        latest_path = posixpath.join(_save_to, _save_latest_format.format("alert.jpg"))
        _cam = self.camera
        _file = self.file_id
        _size = len(self.payload) if self.payload else 0

        message = None
        error = None
        try:
            with open(latest_path, "wb") as fh:
                fh.write(base64.b64decode(str(self.payload)))
                # fh.write(self.binary) # TODO - use this instead
                message = "Saved latest image from [{}] to {} - size {}".format(_cam, _file, _size)
        except IOError as ex:
            error = "[ERROR {}] Could not save image: [{}] to {} - size {}".format(ex, _cam, _file, _size)

        return message, error

    def save_full_sized(self):
        _save_to = self.get_setting('saving', 'path_to_save_images')
        _cam = self.camera
        _file = self.file_id
        _size = len(self.payload) if self.payload else 0

        path = posixpath.join(_save_to, self.file_id)

        message = None
        error = None

        try:
            with open(path, "wb") as fh:
                fh.write(base64.b64decode(str(self.payload)))
                # fh.write(self.binary) # TODO - use this instead
                message = "Saved an image from [{}] to {} - size {}".format(_cam, _file, _size)

        except TypeError as ex:
            error = "[ERROR {}] Could not save image: [{}] to {} - size {}".format(ex, _cam, _file, _size)
        # TODO: Improve Error catching

        return message, error

    def clean_image_folders(self):
        # Delete old files in image directories
        _days_to_keep = self.get_setting('saving', 'days_to_keep_images')
        if _days_to_keep and int(_days_to_keep) > 0:
            _save_loc = self.get_setting('saving', 'path_to_save_images')
            _thumbnails_subdir = self.get_setting('saving', 'thumbnails_subdir')
            _thumbnail_path = posixpath.join(_save_loc, _thumbnails_subdir)

            remove_files_older_than(_save_loc, _days_to_keep)
            remove_files_older_than(_thumbnail_path, _days_to_keep)

    # ---------------------------------------------

    def get_setting(self, d1, d2):
        if d1 in self._settings:
            if d2 in self._settings[d1]:
                return self._settings[d1][d2]
            else:
                self.log('[ERROR] the setting {} not found in config.{}'.format(d2, d1))
        else:
            self.log('[ERROR] the setting config.{} not found'.format(d1))
        return None

    def log(self, message):
        # TODO: Do somethings with these
        pass


# ---------------------------------------------

def remove_files_older_than(dir_path, limit_days):
    threshold = time.time() - limit_days * 86400
    entries = os.listdir(dir_path)
    for file in entries:
        file_pointer = os.path.join(dir_path, file)
        creation_time = os.stat(file_pointer).st_ctime
        if creation_time < threshold:
            os.remove(file_pointer)
