# Recorded test runs

Output of `./run_ipad_tests.sh`, committed so the results can be read
without running anything. Regenerate with `./run_ipad_tests.sh --record`.

**These run on Linux, not on an iPad.** They cover the matching logic and
the adapters around it, using mocks in place of PhotoKit and Scriptable.
Nothing here proves behaviour on a physical device — see the
"What is not covered" section at the bottom.

```
Recorded: 2026-08-11 20:27:21 UTC
Python:   Python 3.11.15
Node:     v22.22.2
Pillow:   12.3.0
Platform: Linux 6.18.5-fc-v20

########################################
# Suite 1: photo dedupe (Python)
########################################

Photo dedupe test suite
========================================
Fixture: 9 files, 4 of which are duplicates of the other 5.

photo_dedupe.py -- desktop, quarantine workflow
-----------------------------------------------
  PASS  dry run reports 2 groups
  PASS  dry run finds the exact trio
  PASS  keeps the clean name, not 'copy'
  PASS  moves nothing without --apply
  PASS  distance 6 also catches the downscale
  PASS  distance 6 finds 4 extras
  PASS  apply leaves exactly the 5 distinct photos
  PASS  apply keeps IMG_0001.jpg
  PASS  apply removed the copies
  PASS  apply never touched unique photos
  PASS  apply wrote an undo manifest
  PASS  rescan after apply is clean
  PASS  restore reports 4 files
  PASS  restore brings everything back

ipad_dedupe.py -- folder mode (same matching as the iPad path)
--------------------------------------------------------------
  PASS  finds the exact group
  PASS  keeps the clean name
  PASS  refuses to delete in folder mode
  PASS  fuzzy finds 3 groups
  PASS  fuzzy finds 4 extras
  PASS  still nothing deleted

ipad_dedupe.py -- library mode against the PhotoKit mock
--------------------------------------------------------
  PASS  library scan sees 9 photos
  PASS  library scan finds 3 groups
  PASS  built a review album
  PASS  album holds exactly the 4 extras
  PASS  album excludes the keepers
  PASS  album mode deleted nothing
  PASS  apply deleted exactly the 4 extras
  PASS  apply left the 5 distinct photos
  PASS  apply mentions Recently Deleted
  PASS  degrades to a report without create_album
  PASS  degraded path deleted nothing

========================================
31 passed, 0 failed

########################################
# Suite 2: job watcher (JavaScript)
########################################

Job watcher test suite
========================================
Fixtures: 3 feeds, 7 postings, 2 of which match the default keywords.
One feed has deliberately wrong field names.

First run, cold state
---------------------
  console output:
    | WARN Arbeitnow: got 1 row(s) but no titles under "title". Actual fields: position, firm, href
    | Remotive: 3 job(s)
    | Arbeitnow: 0 job(s)
    | WeWorkRemotely: 3 job(s)
    | 2 matching, 2 new
  PASS  parses the RSS feed
  PASS  parses the JSON feed
  PASS  matches 2 jobs
  PASS  deduplicates the job shared by two feeds
  PASS  EXCLUDE drops 'Principal Data Engineer'
  PASS  keyword filter drops unrelated jobs
  PASS  reports both new jobs
  PASS  sends one notification
  PASS  notification names the jobs
  PASS  hands a summary back to Shortcuts

Bad field mapping diagnoses itself
----------------------------------
  PASS  warns instead of failing silently
  PASS  prints the real field names
  PASS  a broken feed does not stop the others

Second run, state remembered
----------------------------
    | WARN Arbeitnow: got 1 row(s) but no titles under "title". Actual fields: position, firm, href
    | Remotive: 3 job(s)
    | Arbeitnow: 0 job(s)
    | WeWorkRemotely: 3 job(s)
    | 2 matching, 0 new
  PASS  still matches the same 2 jobs
  PASS  reports 0 new
  PASS  does not re-notify
  PASS  persisted state to disk
  PASS  state holds both job ids

Widget rendering
----------------
  PASS  builds a widget
  PASS  widget shows a heading and rows
  PASS  widget says 'Jobs' when nothing is new

Every feed offline
------------------
    | WARN Remotive failed: Error: simulated network failure
    | WARN Arbeitnow failed: Error: simulated network failure
    | WARN WeWorkRemotely failed: Error: simulated network failure
    | 0 matching, 0 new
  PASS  survives total network failure
  PASS  reports each failure
  PASS  sends no notification when there is nothing

========================================
24 passed, 0 failed

ALL SUITES PASSED
```

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
