import posixpath
import base64
import io
from PIL import Image, UnidentifiedImageError
import os
import time


class Imagery:
    # Manage images

    def __init__(self, file_id, payload, camera, settings, log=None):
        self.file_id = file_id
        self.image = None
        self.camera = camera
        self._settings = settings
        self._log = log
        self.web_url = None
        self.thumbnail_url = None

        if payload:
            try:
                self.image = Image.open(io.BytesIO(base64.b64decode(str(payload))))
            except UnidentifiedImageError as ex:
                self.log("Error {} PIL could not import the included image".format(ex), level="ERROR")

    def save_thumbnail(self):
        # Save a thumbnail of the image
        _save_loc = self.get_setting('saving', 'path_to_save_images')
        _thumbnails_subdir = self.get_setting('saving', 'thumbnails_subdir')
        _thumbnail_path = posixpath.join(_save_loc, _thumbnails_subdir, self.file_id)
        _thumbnails_size = self.get_setting('saving', 'thumbnail_max_size')
        _web_path_to_images = self.get_setting('saving', 'web_path_to_images')
        _size = "unknown"

        try:
            # Also create a thumbnail
            img = self.image.copy()
            img.thumbnail((_thumbnails_size, _thumbnails_size))
            img.save(fp=_thumbnail_path)
            self.thumbnail_url = posixpath.join(_web_path_to_images, _thumbnails_subdir, self.file_id)
            _size = img.size
            self.log("Saved a thumbnail to {}".format(_thumbnail_path), level="INFO")

        except FileNotFoundError as ex:
            self.log("Error {} could not save file {]".format(ex, _thumbnail_path), level="ERROR")
        except ValueError as ex:
            self.log("Error {} saving smaller image {} - {}".format(ex, self.file_id, _size), level="ERROR")

    def save_full_sized(self, save_as_latest=False):
        # Save the image to disk
        if self.image:
            _save_to = self.get_setting('saving', 'path_to_save_images')
            if save_as_latest:
                _save_latest_format = self.get_setting('saving', 'save_latest_format')
                path = posixpath.join(_save_to, _save_latest_format.format("alert"))
            else:
                _web_path_to_images = self.get_setting('saving', 'web_path_to_images')
                path = posixpath.join(_save_to, self.file_id)

                # Also save the web_url to the image
                self.web_url = posixpath.join(_web_path_to_images, self.file_id)

            _cam = self.camera
            _size = self.image.size

            try:
                self.image.save(path)
                self.log("Saved image from [{}] to {} - size {}".format(_cam, path, _size), level="INFO")
            except IOError as ex:
                self.log("Error {} saving : {} to {} - size {}".format(ex, _cam, path, _size), level="ERROR")
        else:
            self.log("Tried to save image that didn't seem to exist", level="ERROR")

    def clean_image_folders(self):
        # Delete old files in image directories
        _days_to_keep = self.get_setting('saving', 'days_to_keep_images')
        if _days_to_keep and int(_days_to_keep) > 0:
            _save_loc = self.get_setting('saving', 'path_to_save_images')
            _thumbnails_subdir = self.get_setting('saving', 'thumbnails_subdir')
            _thumbnail_path = posixpath.join(_save_loc, _thumbnails_subdir)

            self.remove_files_older_than(_save_loc, _days_to_keep)
            self.remove_files_older_than(_thumbnail_path, _days_to_keep)

    def get_piece_of_image(self, rectangle, padding=0):
        if self.image and self.image.width and self.image.height:
            crop_to = get_rectangle_coordinates(rectangle, self.image.width, self.image.height, padding=padding)
            return self.image.crop((crop_to[0], crop_to[1], crop_to[2], crop_to[3]))
        return False

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
        else:
            print("LOG: {}, severity: {}".format(message, level))


def get_rectangle_coordinates(rectangle, width, height, padding=0):
    o = [0, 0, 0, 0]

    if (len(rectangle) == 4 and rectangle[0] <= 1.0 and rectangle[1] <= 1.0
            and rectangle[2] <= 1.0 and rectangle[3] <= 1.0):

        # assume the rectangle was given as percentage coordinates
        o[0] = (rectangle[0] * width) - padding
        o[1] = (rectangle[1] * height) - padding
        o[2] = (rectangle[2] * width) + padding
        o[3] = (rectangle[3] * height) + padding
    elif len(rectangle) == 4:
        o[0] = rectangle[0] - padding
        o[1] = rectangle[1] - padding
        o[2] = rectangle[2] + padding
        o[3] = rectangle[3] + padding
    else:
        # Likely invalid rectangle
        pass

    return [clip(o[0], 0, width), clip(o[1], 0, height), clip(o[2], 0, width), clip(o[3], 0, height)]


def clip(val, min_, max_):
    return min_ if val < min_ else max_ if val > max_ else val
