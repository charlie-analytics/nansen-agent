#!/usr/bin/env python3
"""Test suite for the photo dedupe scripts.

    python3 test_dedupe.py

Builds a fixture with known duplicates, then checks three things:

  * photo_dedupe.py end to end through its command line, including that
    --apply really quarantines and --restore really puts everything back.
  * ipad_dedupe.py in folder mode, which is the same matching logic the
    iPad path uses.
  * ipad_dedupe.py in library mode against mock_photos.py, a stand-in for
    Pythonista's PhotoKit bridge.

Exits non-zero if any check fails.
"""

import io
import os
import random
import shutil
import subprocess
import sys
import tempfile
from contextlib import redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
PASSED = []
FAILED = []


def check(label, condition, detail=""):
    if condition:
        PASSED.append(label)
        print("  PASS  " + label)
    else:
        FAILED.append(label)
        print("  FAIL  " + label + ((" -- " + detail) if detail else ""))


def section(title):
    print("\n" + title)
    print("-" * len(title))


def build_fixture(root):
    """Nine files with a known answer:

      IMG_0001.jpg + 2 byte-identical copies   -> one exact group, 2 extras
      IMG_0002.jpg + a downscaled re-save      -> near group, only at distance>0
      IMG_0003.jpg + a same-size re-save       -> near group, even at distance 0
      IMG_0004.jpg, shot1.png                  -> unique, must never be touched
    """
    from PIL import Image, ImageDraw

    camera = os.path.join(root, "Camera Roll")
    shots = os.path.join(root, "Screenshots")
    os.makedirs(camera)
    os.makedirs(shots)

    def make(path, seed, size=(640, 480)):
        random.seed(seed)
        image = Image.new("RGB", size)
        draw = ImageDraw.Draw(image)
        for _ in range(40):
            x, y = random.randint(0, size[0]), random.randint(0, size[1])
            draw.ellipse(
                [x, y, x + random.randint(20, 120), y + random.randint(20, 120)],
                fill=(random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)),
            )
        image.save(path, quality=92)
        return path

    one = make(os.path.join(camera, "IMG_0001.jpg"), 1)
    two = make(os.path.join(camera, "IMG_0002.jpg"), 2)
    three = make(os.path.join(camera, "IMG_0003.jpg"), 3)
    make(os.path.join(camera, "IMG_0004.jpg"), 4)
    make(os.path.join(shots, "shot1.png"), 5, (800, 600))

    shutil.copy(one, os.path.join(camera, "IMG_0001 copy.jpg"))
    shutil.copy(one, os.path.join(shots, "IMG_0001 copy 2.jpg"))

    Image.open(two).resize((320, 240)).save(
        os.path.join(camera, "IMG_0002_small.jpg"), quality=70)
    Image.open(three).save(os.path.join(shots, "IMG_0003_resave.jpg"), quality=60)


def live_files(root):
    found = []
    for base, _dirs, files in os.walk(root):
        if "_duplicates_bin" in base:
            continue
        for name in files:
            found.append(name)
    return sorted(found)


def run_cli(script, args):
    result = subprocess.run(
        [sys.executable, os.path.join(HERE, script)] + args,
        capture_output=True, text=True)
    return result.stdout + result.stderr


# ---------------------------------------------------------------------------


def test_photo_dedupe(root):
    section("photo_dedupe.py -- desktop, quarantine workflow")

    out = run_cli("photo_dedupe.py", [root])
    check("dry run reports 2 groups", "2 duplicate group(s)" in out, out.strip()[:200])
    check("dry run finds the exact trio", "3 extra copy(s)" in out)
    check("keeps the clean name, not 'copy'",
          "keep   IMG_0001.jpg" in out,
          "keeper line was: " + next((l for l in out.splitlines() if "keep" in l), "?"))
    check("moves nothing without --apply", len(live_files(root)) == 9)

    out = run_cli("photo_dedupe.py", [root, "--distance", "6"])
    check("distance 6 also catches the downscale", "3 duplicate group(s)" in out)
    check("distance 6 finds 4 extras", "4 extra copy(s)" in out)

    out = run_cli("photo_dedupe.py", [root, "--distance", "6", "--apply"])
    remaining = live_files(root)
    check("apply leaves exactly the 5 distinct photos", len(remaining) == 5, str(remaining))
    check("apply keeps IMG_0001.jpg", "IMG_0001.jpg" in remaining)
    check("apply removed the copies", "IMG_0001 copy.jpg" not in remaining)
    check("apply never touched unique photos",
          "IMG_0004.jpg" in remaining and "shot1.png" in remaining)

    manifest = None
    for base, _dirs, files in os.walk(root):
        for name in files:
            if name == "undo-manifest.json":
                manifest = os.path.join(base, name)
    check("apply wrote an undo manifest", manifest is not None)

    out = run_cli("photo_dedupe.py", [root, "--distance", "6"])
    check("rescan after apply is clean", "No duplicates found." in out, out.strip()[:200])

    if manifest:
        out = run_cli("photo_dedupe.py", ["--restore", manifest, root])
        check("restore reports 4 files", "Restored 4 file(s)" in out, out.strip()[:200])
        check("restore brings everything back", len(live_files(root)) == 9,
              str(live_files(root)))


def test_ipad_folder_mode(root):
    section("ipad_dedupe.py -- folder mode (same matching as the iPad path)")

    out = run_cli("ipad_dedupe.py", [root])
    check("finds the exact group", "exact match" in out, out.strip()[:200])
    check("keeps the clean name", "keep   IMG_0001.jpg" in out)
    check("refuses to delete in folder mode", "never deletes" in out)

    out = run_cli("ipad_dedupe.py", [root, "--fuzzy", "--distance", "6"])
    check("fuzzy finds 3 groups", "3 group(s)" in out, out.strip()[:200])
    check("fuzzy finds 4 extras", "4 extra copy(s)" in out)
    check("still nothing deleted", len(live_files(root)) == 9)


def test_ipad_library_mode(root):
    section("ipad_dedupe.py -- library mode against the PhotoKit mock")

    sys.path.insert(0, HERE)
    import mock_photos

    sys.modules["photos"] = mock_photos
    mock_photos.load_folder(root)

    if "ipad_dedupe" in sys.modules:
        del sys.modules["ipad_dedupe"]
    import ipad_dedupe

    buffer = io.StringIO()
    with redirect_stdout(buffer):
        ipad_dedupe.main(["--fuzzy", "--distance", "6", "--thorough"])
    out = buffer.getvalue()

    check("library scan sees 9 photos", "Found 9 photo(s)" in out, out.strip()[:200])
    check("library scan finds 3 groups", "3 group(s)" in out)

    albums = mock_photos.albums()
    check("built a review album", len(albums) == 1)
    if albums:
        names = sorted(os.path.basename(a._path) for a in albums[0].assets)
        expected = sorted(["IMG_0001 copy.jpg", "IMG_0001 copy 2.jpg",
                           "IMG_0003_resave.jpg", "IMG_0002_small.jpg"])
        check("album holds exactly the 4 extras", names == expected, str(names))
        check("album excludes the keepers", "IMG_0001.jpg" not in names)
    check("album mode deleted nothing", len(mock_photos.get_assets()) == 9)

    # Now the destructive path.
    mock_photos.load_folder(root)
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        ipad_dedupe.main(["--fuzzy", "--distance", "6", "--thorough", "--apply"])
    out = buffer.getvalue()

    deleted = sorted(os.path.basename(a._path) for a in mock_photos.deleted())
    expected = sorted(["IMG_0001 copy.jpg", "IMG_0001 copy 2.jpg",
                       "IMG_0003_resave.jpg", "IMG_0002_small.jpg"])
    check("apply deleted exactly the 4 extras", deleted == expected, str(deleted))
    check("apply left the 5 distinct photos", len(mock_photos.get_assets()) == 5)
    check("apply mentions Recently Deleted", "Recently Deleted" in out)

    # And the degraded path, when a Pythonista build lacks create_album.
    mock_photos.load_folder(root)
    saved = mock_photos.create_album
    del mock_photos.create_album
    try:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            ipad_dedupe.main(["--fuzzy", "--distance", "6", "--thorough"])
        out = buffer.getvalue()
        check("degrades to a report without create_album",
              "no create_album" in out and "nothing deleted" in out, out.strip()[-200:])
        check("degraded path deleted nothing", len(mock_photos.get_assets()) == 9)
    finally:
        mock_photos.create_album = saved


def main():
    try:
        import PIL  # noqa: F401
    except ImportError:
        print("Pillow is required: pip install pillow")
        return 2

    print("Photo dedupe test suite")
    print("=" * 40)

    root = tempfile.mkdtemp(prefix="dedupe-test-")
    try:
        build_fixture(root)
        print("Fixture: 9 files, 4 of which are duplicates of the other 5.")

        test_photo_dedupe(root)

        shutil.rmtree(root)
        root = tempfile.mkdtemp(prefix="dedupe-test-")
        build_fixture(root)
        test_ipad_folder_mode(root)
        test_ipad_library_mode(root)
    finally:
        shutil.rmtree(root, ignore_errors=True)

    print("\n" + "=" * 40)
    print("{0} passed, {1} failed".format(len(PASSED), len(FAILED)))
    if FAILED:
        for label in FAILED:
            print("  FAILED: " + label)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
