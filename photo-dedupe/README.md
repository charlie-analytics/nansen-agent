# photo-dedupe

Two scripts for finding duplicate photos:

| Script | Runs on | Acts on |
|---|---|---|
| `ipad_dedupe.py` | **iPad/iPhone**, via Pythonista 3 | your real Photos library |
| `photo_dedupe.py` | Mac / PC / Linux | a folder of image files |

## Running it on the iPad

iPadOS only lets a signed app reach the Photos library through Apple's PhotoKit
framework. [Pythonista 3](https://apps.apple.com/us/app/pythonista-3/id1085978097)
is a Python IDE that ships exactly that bridge as its
[`photos` module](https://omz-software.com/pythonista/docs/ios/photos.html), so a
plain Python script can enumerate the library, read original image data and
delete assets. It is a paid app — that is the cost of entry, and there is no free
equivalent with real library access.

1. Install Pythonista 3 from the App Store.
2. Copy `ipad_dedupe.py` into it (paste it, or open it from Files / iCloud Drive).
3. Press Run. Grant photo access when iOS asks.

By default it **deletes nothing**. It finds the duplicates and drops the extra
copies into a new album called **Duplicates to review**. You then open
Photos → Albums → Duplicates to review, flick through them as actual pictures,
and delete the ones you agree with. The originals it decided to keep are never
put in that album, so anything you see there is safe to remove.

That review step matters more than it sounds: duplicates share a capture time, so
a text report of them is a wall of identical timestamps. Reviewing them as images
is the only way to actually check the tool's work.

### If you want it to delete directly

Edit the settings block at the top of the file:

```python
APPLY = True
```

Then it calls `photos.batch_delete()`, which shows the iOS confirmation sheet
once for the whole batch and moves the photos to **Recently Deleted** — where
they stay recoverable for 30 days. Even the aggressive path is reversible.

### Settings

```python
APPLY    = False  # True = go straight to Recently Deleted, skip the album
ALBUM    = True   # gather extras into a review album
FUZZY    = False  # also match resizes / re-saves, not just identical files
DISTANCE = 6      # how alike counts as "the same", 0-16
THOROUGH = False  # compare across capture dates too (see below)
LIMIT    = 0      # only look at the first N photos, 0 = all. Good for a trial run
```

Set `LIMIT = 200` for the first run. It finishes in seconds and shows you what
the matching does on your own photos before you point it at ten thousand of them.

### The two speed/thoroughness tradeoffs

**`THOROUGH`** — normally a photo is only compared against others with the same
dimensions *and* the same capture time. That is what keeps the scan from having
to read every photo in your library. It catches the ordinary case, where a
duplicate carries the same EXIF timestamp as its twin. It will *miss* a duplicate
whose timestamp was rewritten — an image re-saved from Messages, say. `THOROUGH`
drops the timestamp from the comparison and catches those, at the cost of reading
far more photos.

**iCloud.** If Settings → Photos → *Optimize iPad Storage* is on, the
full-resolution originals may not be on the device, and reading them pulls them
down over the network. A thorough scan of a large library on a slow connection is
a genuinely long operation. `LIMIT` is how you find that out cheaply.

**`FUZZY`** is a per-pair comparison, so it costs roughly n². A few thousand
photos is fine; tens of thousands will take a while.

## Running it on a computer

`photo_dedupe.py` is the desktop version, with a quarantine workflow instead of
PhotoKit:

```bash
pip install pillow
python3 photo_dedupe.py ~/Pictures                  # report only
python3 photo_dedupe.py ~/Pictures --distance 6     # catch resizes/re-saves
python3 photo_dedupe.py ~/Pictures --apply          # move extras to a bin
python3 photo_dedupe.py --restore <manifest.json> ~/Pictures
```

`--apply` *moves* extras into `_duplicates_bin/<timestamp>/` next to an
`undo-manifest.json`. Nothing is unlinked; emptying that folder is your call.

`ipad_dedupe.py` also runs on a desktop against a folder (`python3
ipad_dedupe.py ~/Pictures`) in report-only mode — that is how its matching logic
is tested off-device.

## How matching works

1. **Exact** — SHA-256 over the original bytes. Files are pre-filtered into
   buckets that could possibly match (dimensions + capture date on iOS, byte size
   on disk), so photos that are alone in their bucket are never read at all.
2. **Near** (`FUZZY`) — a 64-bit difference hash of a 9×8 greyscale thumbnail.
   Photos within `DISTANCE` bits are clustered with union-find, so a run of
   near-identical burst frames collapses into one group instead of a pile of
   pairs.

`DISTANCE 0` means visually identical — still catches re-saves and quality
changes that byte comparison misses. `4`–`6` also catches resizes and small
crops. Above `10` it starts grouping photos that merely look similar; review the
album before deleting.

**Which copy is kept:** most pixels → largest file → oldest → shortest filename.
The full-resolution original beats the downscaled re-save, and `IMG_0001.jpg`
beats `IMG_0001 copy 2.jpg`.

## What is not covered

- **Video** is skipped entirely on iOS. Perceptual hashing of frames is a
  different problem, and byte-reading movies off iCloud is expensive.
- **HEIC** works for exact matching. Near-duplicate matching needs Pillow to
  decode it — fine in Pythonista, but on desktop it needs `pip install
  pillow-heif`. The run tells you how many files it could not decode.
- **Shared-album and synced assets** cannot be deleted by any app; the script
  checks `can_delete` and leaves them alone.

## Testing status

The matching, grouping and keeper-selection logic is tested against a fixture of
known duplicates — exact copies across folders, a downscaled re-save and a
quality re-save — in both file mode and against a mock of Pythonista's `photos`
API. The mock covers `get_assets`, `get_image_data`, `create_album` and
`batch_delete`.

The PhotoKit calls themselves have **not** been run on a physical device. Every
call into the `photos` module is feature-detected and wrapped, so a missing or
changed API degrades to a plain report rather than misbehaving — but the first
real run is still a first real run. Use `LIMIT` and the review album for it.

## Before you install anything

iPadOS 16 and later has duplicate detection built into Photos:
**Photos → Utilities → Duplicates**. It finds exact and near duplicates and its
*Merge* keeps the highest-quality copy while combining metadata. It costs
nothing and takes two minutes.

These scripts are for what that screen does not give you: control over the
matching threshold, control over which copy survives, a written report, and
duplicates that Apple's detector groups differently than you would.
