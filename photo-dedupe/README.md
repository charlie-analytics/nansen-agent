# photo-dedupe

Finds duplicate photos in a folder and quarantines the extra copies. Single file,
no dependencies beyond Pillow (optional).

## Important: this does not run on an iPad

iPadOS does not let a script reach the Photos library — only a signed app using
Apple's PhotoKit framework can read or delete photos, and there is no Python
runtime with that access. This tool runs on a **Mac, PC, or Linux box**, against a
folder of photo *files*.

For deduping directly on the iPad, Photos has this built in:
**Photos → Utilities → Duplicates**. It finds exact and near-duplicates and its
"Merge" keeps the highest-quality copy while combining the metadata. That is the
right first stop; this script is for when you have the photos on a computer and
want control over the matching, the keeper choice, and the audit trail.

## Usage

```bash
pip install pillow           # optional, enables near-duplicate matching

python3 photo_dedupe.py ~/Pictures                    # dry run, report only
python3 photo_dedupe.py ~/Pictures --distance 6       # also catch resizes/re-saves
python3 photo_dedupe.py ~/Pictures --apply            # quarantine the extras
python3 photo_dedupe.py --restore <manifest.json> ~/Pictures   # undo
```

Nothing is deleted, ever. `--apply` *moves* extras into `_duplicates_bin/<timestamp>/`
next to an `undo-manifest.json`. Deleting is your call — empty that folder when
you have looked at what is in it.

## How matching works

1. **Exact** — SHA-256 over the file bytes, bucketed by file size first so most
   files are never hashed. Works on any format, including HEIC and video.
2. **Near** — a 64-bit difference hash (dHash) of a decoded 9×8 greyscale
   thumbnail. Photos within `--distance` bits of each other are clustered with
   union-find, so a chain of near-identical burst frames collapses into one group.

`--distance 0` (the default) means visually identical — it still catches re-saves
and quality changes that byte-comparison misses. `4`–`6` also catches resizes and
crops. Above `10` it starts grouping photos that merely look alike; check the
report before applying.

## Which copy is kept

Most pixels → largest file → oldest → shortest filename. So the full-resolution
original beats the downscaled re-save, and `IMG_0042.jpg` beats
`IMG_0042 copy 2.jpg`. Every group's keeper is printed in the report before
anything moves.

## Limits

- HEIC/HEIF need `pip install pillow-heif` for near-duplicate matching. Without
  it they still get exact matching; the run tells you how many were skipped.
- Near-duplicate matching with `--distance > 0` is pairwise. ~20k photos takes a
  couple of minutes of comparison on top of decoding time.
- Videos get exact matching only — no perceptual hashing of frames.
