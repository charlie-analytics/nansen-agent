# coding: utf-8
"""Pythonista self-test — run this ON the iPad before trusting ipad_dedupe.py.

It answers what I could not answer from a Linux container: does this Pythonista
build expose the PhotoKit calls the deduper needs, and are the Asset attribute
names what the script assumes?

Strictly read-only. It creates nothing, deletes nothing, and modifies nothing.
It reads image data for a single photo to time it, and that is the most
invasive thing it does. The report is copied to your clipboard at the end.

Python 3.6 compatible, same as ipad_dedupe.py.
"""

import sys
import time

LINES = []


def out(text=""):
    LINES.append(text)
    print(text)


out("Pythonista self-test")
out("=" * 34)

# --- the photos module -----------------------------------------------------

try:
    import photos
except ImportError:
    out("")
    out("FAILED: no `photos` module.")
    out("This is not Pythonista, or photo access was denied.")
    out("ipad_dedupe.py cannot work here.")
    raise SystemExit(1)

out("")
out("Module functions")
missing = 0
for name in ("get_assets", "get_albums", "get_smart_albums", "create_album",
             "batch_delete", "pick_asset"):
    present = hasattr(photos, name)
    # Only the first, create_album and batch_delete actually gate the deduper.
    required = name in ("get_assets", "batch_delete")
    if not present and required:
        missing += 1
    out("  " + ("ok      " if present else ("MISSING " if required else "absent  ")) + name)

# --- the library ------------------------------------------------------------

out("")
out("Library")
try:
    started = time.time()
    assets = photos.get_assets()
    out("  {0} asset(s) listed in {1:.1f}s".format(len(assets), time.time() - started))
except Exception as exc:
    out("  FAILED to list assets: {0}".format(exc))
    raise SystemExit(1)

if not assets:
    out("  No photos found — nothing further to check.")
    raise SystemExit(0)

images = []
for asset in assets:
    if getattr(asset, "media_type", "image") == "image":
        images.append(asset)
out("  {0} of them are images".format(len(images)))

# --- Asset attributes the deduper reads -------------------------------------

sample = images[0] if images else assets[0]

out("")
out("Asset attributes")
for name in ("pixel_width", "pixel_height", "creation_date", "modification_date",
             "media_type", "local_id", "can_delete", "hidden", "favorite"):
    if hasattr(sample, name):
        value = getattr(sample, name)
        out("  ok      {0} = {1}".format(name, str(value)[:40]))
    else:
        # pixel_width/height and creation_date drive the whole pre-filter.
        critical = name in ("pixel_width", "pixel_height", "creation_date")
        if critical:
            missing += 1
        out("  {0}{1}".format("MISSING " if critical else "absent  ", name))

out("")
out("  Other attributes this build exposes:")
extras = [n for n in dir(sample) if not n.startswith("_")]
out("    " + ", ".join(extras[:24]))

# --- reading image data -----------------------------------------------------

out("")
out("Reading image data (the slow part on iCloud libraries)")
try:
    started = time.time()
    handle = sample.get_image_data(original=True)
    payload = handle.getvalue()
    elapsed = time.time() - started
    out("  ok      read {0} bytes in {1:.2f}s".format(len(payload), elapsed))
    out("  uti:    {0}".format(getattr(handle, "uti", "(none)")))
    try:
        handle.close()
    except Exception:
        pass
    del payload

    estimate = elapsed * len(images)
    out("  At that rate, reading every image would take about "
        "{0:.0f} minute(s).".format(estimate / 60.0))
    out("  (The deduper only reads photos that share size and date with another,")
    out("   so the real scan is far quicker than that number.)")
except Exception as exc:
    missing += 1
    out("  FAILED: {0}".format(exc))

# --- decoding, for near-duplicate matching ----------------------------------

out("")
out("Decoding for near-duplicate matching")
try:
    from PIL import Image  # noqa: F401
    out("  ok      PIL available")
    try:
        image = sample.get_image()
        out("  ok      get_image() returned {0} {1}".format(
            type(image).__name__, getattr(image, "size", "")))
        try:
            image.close()
        except Exception:
            pass
    except Exception as exc:
        out("  FAILED  get_image(): {0}".format(exc))
        out("          Exact matching still works; set FUZZY = False.")
except ImportError:
    out("  absent  PIL — exact matching only, set FUZZY = False.")

# --- verdict ----------------------------------------------------------------

out("")
out("=" * 34)
if missing:
    out("{0} required capability(s) missing.".format(missing))
    out("ipad_dedupe.py will not work correctly on this build.")
else:
    out("Everything ipad_dedupe.py needs is present.")
    out("Start it with LIMIT = 200 and leave APPLY = False.")

try:
    import clipboard
    clipboard.set("\n".join(LINES))
    out("")
    out("(Report copied to your clipboard — paste it back to share it.)")
except Exception:
    pass
