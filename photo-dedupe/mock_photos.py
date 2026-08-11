# coding: utf-8
"""Stand-in for Pythonista's `photos` module, matching the documented API:
get_assets(), batch_delete(assets), and Asset objects exposing pixel_width,
pixel_height, creation_date, media_type, local_id, get_image_data(original=)
returning an io.BytesIO, and get_image() returning a PIL Image.
"""

import io
import os
from datetime import datetime

from PIL import Image

_DELETED = []


class Asset(object):
    def __init__(self, path, created, local_id, media_type="image"):
        self._path = path
        self.creation_date = created
        self.local_id = local_id
        self.media_type = media_type
        self.can_delete = True
        with Image.open(path) as img:
            self.pixel_width, self.pixel_height = img.size

    def get_image_data(self, original=True):
        with open(self._path, "rb") as fh:
            buffer = io.BytesIO(fh.read())
        buffer.uti = "public.jpeg"
        return buffer

    def get_image(self):
        return Image.open(self._path)

    def __repr__(self):
        return "<Asset {0}>".format(os.path.basename(self._path))


_ASSETS = []


def load_folder(folder):
    del _ASSETS[:]
    del _DELETED[:]
    index = 0
    for base, _dirs, files in os.walk(folder):
        for name in sorted(files):
            if not name.lower().endswith((".jpg", ".jpeg", ".png")):
                continue
            path = os.path.join(base, name)
            stamp = datetime.fromtimestamp(os.path.getmtime(path))
            _ASSETS.append(Asset(path, stamp, "id-{0}".format(index)))
            index += 1
    return _ASSETS


class AssetCollection(object):
    def __init__(self, title):
        self.title = title
        self.assets = []

    def add_assets(self, assets):
        self.assets.extend(assets)


_ALBUMS = []


def create_album(title):
    album = AssetCollection(title)
    _ALBUMS.append(album)
    return album


def albums():
    return list(_ALBUMS)


def get_assets():
    return list(_ASSETS)


def batch_delete(assets):
    _DELETED.extend(assets)
    for asset in assets:
        if asset in _ASSETS:
            _ASSETS.remove(asset)
    return True


def deleted():
    return list(_DELETED)
