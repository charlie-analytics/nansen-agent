# coding: utf-8
"""Find duplicate photos, on the iPad itself.

One file, two environments:

  * Pythonista 3 on iPadOS -> reads the real Photos library through PhotoKit,
    and can send duplicates to Recently Deleted.
  * Any desktop Python -> scans a folder of image files, so the grouping logic
    can be tested off-device.

Report-only unless you turn on APPLY. On iOS, applying hands the extra copies
to photos.batch_delete(), which shows the system confirmation sheet and moves
them to Recently Deleted -- where iOS keeps them for 30 days before purging.
Nothing is destroyed immediately.

Written for Python 3.6, which is what Pythonista ships. No dataclasses, no
walrus, no PEP 604 unions.
"""

import hashlib
import io
import os
import sys
from collections import defaultdict

# ---------------------------------------------------------------------------
# Settings used when the script is launched with no command-line arguments.
# Pythonista's Run button passes none, so edit these directly on the iPad.
# ---------------------------------------------------------------------------
APPLY = False       # True = hand the extras straight to Recently Deleted
ALBUM = True        # True = gather the extras into an album to review first
FUZZY = False       # True = also catch resizes and re-saves (much slower)
DISTANCE = 6        # bit tolerance for FUZZY, 0-16
THOROUGH = False    # True = compare across capture dates too (slower, safer)
LIMIT = 0           # cap how many photos to look at, 0 = no cap
FOLDER = None       # desktop only: folder to scan

ALBUM_TITLE = "Duplicates to review"

try:
    import photos as ios_photos
except ImportError:
    ios_photos = None

try:
    from PIL import Image
except ImportError:
    Image = None

HASH_SIDE = 8
IMAGE_SUFFIXES = (".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tif", ".tiff",
                  ".webp", ".heic", ".heif")


# ---------------------------------------------------------------------------
# Items: a uniform wrapper over "a photo in the library" and "a file on disk",
# so every grouping function below works identically in both environments.
# ---------------------------------------------------------------------------

class LibraryItem(object):
    """A PhotoKit asset from the on-device Photos library."""

    def __init__(self, asset):
        self.asset = asset
        self.width = int(getattr(asset, "pixel_width", 0) or 0)
        self.height = int(getattr(asset, "pixel_height", 0) or 0)
        self.created = getattr(asset, "creation_date", None)
        self.digest = ""
        self.dhash = None
        self.nbytes = 0

    @property
    def pixels(self):
        return self.width * self.height

    @property
    def name(self):
        stamp = self.created.strftime("%Y-%m-%d %H:%M:%S") if self.created else "no date"
        # Duplicates share a capture time by definition, so the id fragment is
        # what actually tells two rows of the report apart.
        tag = str(getattr(self.asset, "local_id", ""))[:8]
        size = " {0}".format(human(self.nbytes)) if self.nbytes else ""
        return "{0} {1}x{2}{3} [{4}]".format(stamp, self.width, self.height, size, tag)

    @property
    def sort_name(self):
        # Library assets have no user-facing filename to prefer between, so
        # this only ever acts as a stable last-resort tiebreak.
        return str(getattr(self.asset, "local_id", ""))

    def bucket_key(self, thorough):
        # PhotoKit hands us dimensions and dates for free, but file size only
        # by reading the asset -- so pre-filter on what is already in memory.
        if thorough:
            return (self.width, self.height)
        stamp = self.created.strftime("%Y%m%d%H%M%S") if self.created else "?"
        return (self.width, self.height, stamp)

    def read_bytes(self):
        """Full original bytes. On a library with Optimize Storage enabled this
        may pull the original down from iCloud, which is the slow part."""
        handle = self.asset.get_image_data(original=True)
        try:
            payload = handle.getvalue()
        finally:
            # get_image_data has a history of holding memory; drop it promptly.
            try:
                handle.close()
            except Exception:
                pass
        self.nbytes = len(payload)
        return payload

    def open_image(self):
        return self.asset.get_image()


class FileItem(object):
    """An image file on disk (desktop mode)."""

    def __init__(self, path):
        self.path = path
        self.nbytes = os.path.getsize(path)
        self.created = None
        self.width = 0
        self.height = 0
        self.digest = ""
        self.dhash = None
        self._measured = False

    def _measure(self):
        if self._measured or Image is None:
            return
        self._measured = True
        try:
            with Image.open(self.path) as img:
                self.width, self.height = img.size
        except Exception:
            pass

    @property
    def pixels(self):
        self._measure()
        return self.width * self.height

    @property
    def name(self):
        return "{0} ({1}KB)".format(os.path.basename(self.path), self.nbytes // 1024)

    @property
    def sort_name(self):
        return os.path.basename(self.path)

    def bucket_key(self, thorough):
        # On disk the byte size is free from stat() and is a stricter filter
        # than dimensions, so decoding is never needed just to pre-filter.
        return self.nbytes

    def read_bytes(self):
        with open(self.path, "rb") as fh:
            return fh.read()

    def open_image(self):
        return Image.open(self.path)


# ---------------------------------------------------------------------------
# Hashing
# ---------------------------------------------------------------------------

def dhash_bits(image):
    """64-bit difference hash: compare each pixel to its right-hand neighbour."""
    small = image.convert("L").resize((HASH_SIDE + 1, HASH_SIDE), Image.LANCZOS)
    data = list(small.tobytes())
    bits = 0
    for row in range(HASH_SIDE):
        offset = row * (HASH_SIDE + 1)
        for col in range(HASH_SIDE):
            bits = (bits << 1) | int(data[offset + col] > data[offset + col + 1])
    return bits


def popcount(value):
    return bin(value).count("1")


# ---------------------------------------------------------------------------
# Grouping
# ---------------------------------------------------------------------------

def pick_keeper(items):
    """Best copy wins: most pixels, then biggest file, then oldest. The name
    length tiebreak matters for byte-identical copies, where nothing else
    discriminates -- it keeps "IMG_0001.jpg" over "IMG_0001 copy 2.jpg"."""
    def rank(item):
        stamp = item.created.timestamp() if item.created else 0
        return (-item.pixels, -item.nbytes, stamp,
                len(item.sort_name), item.sort_name)
    return min(items, key=rank)


def bucket_candidates(items, thorough):
    """Cheap pre-filter. Two photos can only be byte-identical if they share
    dimensions, so anything alone in its bucket never needs its data read --
    which is what keeps this from downloading an entire iCloud library."""
    buckets = defaultdict(list)
    for item in items:
        buckets[item.bucket_key(thorough)].append(item)
    return [group for group in buckets.values() if len(group) > 1]


def find_exact(items, thorough, progress=None):
    groups = []
    candidates = bucket_candidates(items, thorough)
    total = sum(len(c) for c in candidates)
    seen = 0

    for candidate in candidates:
        by_digest = defaultdict(list)
        for item in candidate:
            try:
                payload = item.read_bytes()
            except Exception:
                seen += 1
                continue
            item.digest = hashlib.sha256(payload).hexdigest()
            del payload
            by_digest[item.digest].append(item)
            seen += 1
            if progress and seen % 25 == 0:
                progress(seen, total)
        for matches in by_digest.values():
            if len(matches) > 1:
                keeper = pick_keeper(matches)
                groups.append(("exact", keeper,
                               [m for m in matches if m is not keeper]))
    return groups


def find_fuzzy(items, distance):
    """Union-find over perceptual hashes, so a chain of near-identical burst
    frames collapses into a single group rather than a pile of pairs."""
    hashed = [i for i in items if i.dhash is not None]
    parent = list(range(len(hashed)))

    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(a, b):
        ra, rb = root(a), root(b)
        if ra != rb:
            parent[rb] = ra

    if distance == 0:
        buckets = defaultdict(list)
        for index, item in enumerate(hashed):
            buckets[item.dhash].append(index)
        for members in buckets.values():
            for other in members[1:]:
                union(members[0], other)
    else:
        for i in range(len(hashed)):
            for j in range(i + 1, len(hashed)):
                if popcount(hashed[i].dhash ^ hashed[j].dhash) <= distance:
                    union(i, j)

    clusters = defaultdict(list)
    for index, item in enumerate(hashed):
        clusters[root(index)].append(item)

    groups = []
    for members in clusters.values():
        if len(members) > 1:
            keeper = pick_keeper(members)
            groups.append(("near", keeper,
                           [m for m in members if m is not keeper]))
    return groups


def human(size):
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return "{0:.1f}{1}".format(value, unit)
        value /= 1024
    return "{0:.1f}GB".format(value)


def build_report(groups, scanned):
    lines = ["Scanned {0} photo(s)".format(scanned)]
    if not groups:
        lines.append("No duplicates found.")
        return lines, 0, 0

    extras = sum(len(g[2]) for g in groups)
    reclaim = sum(sum(e.nbytes for e in g[2]) for g in groups)
    lines.append("")
    lines.append("{0} group(s), {1} extra copy(s), {2} reclaimable".format(
        len(groups), extras, human(reclaim)))
    lines.append("")
    for index, group in enumerate(groups, 1):
        kind, keeper, dupes = group
        lines.append("[{0}] {1} match".format(index, kind))
        lines.append("    keep   " + keeper.name)
        for dupe in dupes:
            lines.append("    extra  " + dupe.name)
    return lines, extras, reclaim


# ---------------------------------------------------------------------------
# Environments
# ---------------------------------------------------------------------------

def gather_library(limit):
    assets = ios_photos.get_assets()
    items = []
    for asset in assets:
        # Skip video: perceptual hashing of frames is out of scope, and byte
        # comparison on large movies is not worth the read cost.
        if getattr(asset, "media_type", "image") != "image":
            continue
        items.append(LibraryItem(asset))
        if limit and len(items) >= limit:
            break
    return items


def gather_folder(folder, limit):
    items = []
    for base, _dirs, files in os.walk(folder):
        for filename in sorted(files):
            if filename.startswith("."):
                continue
            if not filename.lower().endswith(IMAGE_SUFFIXES):
                continue
            path = os.path.join(base, filename)
            try:
                if os.path.getsize(path) == 0:
                    continue
            except OSError:
                continue
            items.append(FileItem(path))
            if limit and len(items) >= limit:
                return items
    return items


def collect_album(groups, title):
    """Gather the extras into an album so they can be reviewed as pictures in
    the Photos app. Far safer than acting on a report where every duplicate
    shows the same capture time -- you see what you are about to lose."""
    extras = []
    for _kind, _keeper, dupes in groups:
        extras.extend(dupe.asset for dupe in dupes)
    if not extras:
        return False

    creator = getattr(ios_photos, "create_album", None)
    if creator is None:
        print("This Pythonista build has no create_album(); skipping album.")
        return False

    try:
        album = creator(title)
        adder = getattr(album, "add_assets", None)
        if adder is None:
            adder = getattr(album, "add_asset", None)
            if adder is None:
                print("Album created but assets could not be added.")
                return False
            for asset in extras:
                adder(asset)
        else:
            adder(extras)
    except Exception as exc:
        print("Could not build the album: {0}".format(exc))
        return False

    print("\nAlbum '{0}' now holds {1} duplicate(s).".format(title, len(extras)))
    print("Open Photos > Albums > {0}, look through them, and delete the "
          "ones you agree with.".format(title))
    print("The originals were left untouched and are not in that album.")
    return True


def apply_library(groups):
    """Hand the extras to PhotoKit. iOS shows one confirmation sheet for the
    whole batch, then moves them to Recently Deleted (30-day grace period)."""
    extras = []
    for _kind, _keeper, dupes in groups:
        for dupe in dupes:
            if getattr(dupe.asset, "can_delete", True):
                extras.append(dupe.asset)
    if not extras:
        print("Nothing deletable -- the extras are read-only assets.")
        return
    print("\nAsking iOS to delete {0} photo(s)...".format(len(extras)))
    try:
        confirmed = ios_photos.batch_delete(extras)
    except Exception as exc:
        print("Delete failed: {0}".format(exc))
        return
    if confirmed is False:
        print("Cancelled -- nothing was deleted.")
    else:
        print("Moved to Recently Deleted. Recoverable there for 30 days.")


def parse_args(argv):
    settings = {"apply": APPLY, "album": ALBUM, "fuzzy": FUZZY,
                "distance": DISTANCE, "thorough": THOROUGH, "limit": LIMIT,
                "folder": FOLDER}
    rest = []
    index = 0
    while index < len(argv):
        arg = argv[index]
        if arg == "--apply":
            settings["apply"] = True
        elif arg == "--no-album":
            settings["album"] = False
        elif arg == "--fuzzy":
            settings["fuzzy"] = True
        elif arg == "--thorough":
            settings["thorough"] = True
        elif arg == "--distance":
            index += 1
            settings["distance"] = int(argv[index])
        elif arg == "--limit":
            index += 1
            settings["limit"] = int(argv[index])
        elif arg.startswith("-"):
            raise SystemExit("unknown option: " + arg)
        else:
            rest.append(arg)
        index += 1
    if rest:
        settings["folder"] = rest[0]
    return settings


def main(argv):
    settings = parse_args(argv)
    on_device = ios_photos is not None

    if on_device:
        print("Reading the Photos library...")
        items = gather_library(settings["limit"])
    else:
        folder = settings["folder"]
        if not folder:
            raise SystemExit(
                "Desktop mode needs a folder: python3 ipad_dedupe.py ~/Pictures")
        if not os.path.isdir(folder):
            raise SystemExit("not a folder: " + folder)
        items = gather_folder(folder, settings["limit"])

    print("Found {0} photo(s).".format(len(items)))
    if not items:
        return 0

    # Pythonista's console does not reliably honour carriage-return erasure,
    # so report progress as discrete lines and only when the wait is long
    # enough to be worth narrating.
    def progress(done, total):
        if total > 100:
            print("  hashing {0}/{1}".format(done, total))

    groups = find_exact(items, settings["thorough"], progress)

    if settings["fuzzy"]:
        if Image is None:
            print("note: PIL unavailable, skipping near-duplicate matching.")
        else:
            claimed = set()
            for _kind, keeper, dupes in groups:
                claimed.add(id(keeper))
                for dupe in dupes:
                    claimed.add(id(dupe))
            remaining = [i for i in items if id(i) not in claimed]
            print("Perceptual pass over {0} photo(s)...".format(len(remaining)))
            for position, item in enumerate(remaining):
                try:
                    image = item.open_image()
                    item.dhash = dhash_bits(image)
                    if not item.nbytes:
                        item.width, item.height = image.size
                    try:
                        image.close()
                    except Exception:
                        pass
                except Exception:
                    item.dhash = None
                if len(remaining) > 100 and position % 100 == 0 and position:
                    print("  reading {0}/{1}".format(position, len(remaining)))
            groups.extend(find_fuzzy(remaining, settings["distance"]))

    groups.sort(key=lambda g: -sum(e.nbytes for e in g[2]))
    lines, extras, _reclaim = build_report(groups, len(items))
    text = "\n".join(lines)
    print(text)

    if groups:
        try:
            report_path = os.path.join(os.path.expanduser("~/Documents"),
                                       "duplicate-report.txt")
            with io.open(report_path, "w", encoding="utf-8") as fh:
                fh.write(text + "\n")
            print("\nReport saved to " + report_path)
        except Exception:
            pass

    if not groups:
        return 0

    if not on_device:
        print("\nDesktop mode never deletes. Use photo_dedupe.py --apply for "
              "the quarantine workflow.")
        return 0

    if settings["apply"]:
        apply_library(groups)
        return 0

    if settings["album"] and collect_album(groups, ALBUM_TITLE):
        return 0

    print("\nReport only -- nothing deleted.")
    print("Set APPLY = True at the top of this file to delete the extras.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
