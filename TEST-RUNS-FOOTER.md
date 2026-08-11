## What these runs prove

**photo_dedupe.py** — genuinely exercised end to end. The suite drives the real
command line against a real fixture on disk: it checks that a dry run moves
nothing, that `--apply` quarantines exactly the 4 duplicate files and leaves the
5 distinct ones, that a rescan afterwards is clean, and that `--restore` puts all
9 files back. This one is production-ready on a computer.

**ipad_dedupe.py, folder mode** — the same matching logic the iPad path uses,
run for real against files.

**ipad_dedupe.py, library mode** — run against `mock_photos.py`, a stand-in
implementing Pythonista's documented `photos` API (`get_assets`,
`get_image_data`, `create_album`, `batch_delete`). This proves the adapter logic
is correct: the review album receives exactly the 4 extras and none of the
keepers, `--apply` deletes exactly those 4, and a build without `create_album`
degrades to a plain report instead of misbehaving.

**job_watcher.js** — run against a stubbed Scriptable runtime with fixture
feeds. Proves RSS and JSON parsing, keyword and exclusion filtering,
deduplication of a job appearing in two feeds, state persistence across runs,
widget construction, the self-diagnosing warning when a feed's field names are
wrong, and survival when every feed is offline.

## What is not covered

Three gaps, all of which need a device or a network I do not have:

1. **No run on a physical iPad.** PhotoKit and Scriptable are mocked. The mocks
   follow the documented APIs, and every call into them is feature-detected and
   wrapped so a mismatch degrades to a report — but a mock agreeing with itself
   is not the same as iOS agreeing with it.

2. **No live feed calls.** This environment's network policy returns 403 for the
   job-board hosts, so the JSON field mappings in `job_watcher.js` are unverified
   against real responses. The script prints the real field names when a mapping
   is wrong, which turns a silent failure into a one-line fix.

3. **The Shortcuts builds are untested entirely.** They are written from Apple's
   documented triggers and actions, not built on a device. The Email and Message
   triggers are historically unreliable on iOS regardless of how they are built.

## Reading a failure

Each suite exits non-zero if anything fails, and prints a `FAILED:` list at the
end. `run_ipad_tests.sh` propagates that, so it is safe to wire into CI.
