# iPad tools

Everything here was built to run on an iPad. This page says what actually runs
there, what it needs, and how far each one has been tested.

Recorded test output: **[TEST-RUNS.md](TEST-RUNS.md)** — 55 checks, all passing.
Re-run it yourself with `./run_ipad_tests.sh`.

## What runs on the iPad

| Tool | Needs | Cost | Tested how far |
|---|---|---|---|
| [`ipad_dedupe.py`](photo-dedupe/ipad_dedupe.py) — find duplicate photos | Pythonista 3 | paid, ~$10 | logic + PhotoKit mock, **not on a device** |
| [`job_watcher.js`](ipad-agents/job_watcher.js) — watch job feeds | Scriptable | free | logic + runtime stubs, **not on a device** |
| [Job alerts from email](ipad-agents/SHORTCUTS.md#1-job-alerts-from-linkedin-without-touching-linkedin) | Shortcuts | built in | **not tested** — build steps only |
| [Message triage](ipad-agents/SHORTCUTS.md#2-message-triage) | Shortcuts | built in | **not tested** — build steps only |
| [Storage cleanup](ipad-agents/SHORTCUTS.md#3-storage-cleanup) | Shortcuts | built in | **not tested** — build steps only |

## What runs on a computer, not the iPad

| Tool | Tested how far |
|---|---|
| [`photo_dedupe.py`](photo-dedupe/photo_dedupe.py) — dedupe a photo folder | end to end, for real. Ready to use. |

## Honest status

I have no iPad. **Nothing in the first table has ever run on a physical
device.** The tests cover the logic and the adapters, with mocks standing in for
PhotoKit and Scriptable, so a mistake in my reasoning would be caught — but a
mistake in my assumptions about iOS would not.

That splits into three confidence levels:

**Solid.** `photo_dedupe.py` on a computer. The suite drives its real command
line against real files: `--apply` quarantines exactly the duplicates, a rescan
comes back clean, `--restore` puts all 9 files back. Use it today.

**Likely to work, verify on first run.** `ipad_dedupe.py` and `job_watcher.js`.
The logic is tested hard, the API calls follow published documentation, and both
degrade to a harmless report rather than misbehaving if an API differs. Their
first real run is still their first real run — which is why the photo tool
defaults to a review album instead of deleting, and why `LIMIT = 200` exists.

**Unverified.** The three Shortcuts builds. Written from Apple's documented
triggers, never built on a device. The Email and Message triggers are known to
be unreliable on iOS regardless.

## Suggested order

1. **Photos → Utilities → Duplicates** — already on your iPad, free, two
   minutes. Try this before installing anything.
2. **Storage cleanup shortcut** — no triggers involved, so it is the one most
   likely to just work. A good feel for how Shortcuts behaves.
3. **`job_watcher.js` in Scriptable** — free. If it shows jobs, it works.
4. **Job alert emails** — the useful one, but leans on the flakiest iOS trigger.
5. **`ipad_dedupe.py` in Pythonista** — last, because it is the only one that
   costs money. Only if step 1 was not enough.

## The rule behind all of this

An iPad app can only reach data Apple built a bridge for: Photos, Calendar,
Reminders, Contacts, Health, Files, Location, clipboard, notifications, web
requests. Everything above sits on one of those.

There is no bridge to your Messages history, to another app's data, or to
controlling another app's screen. That is why LinkedIn automation is not on this
list, and why the job tooling works by having LinkedIn email you instead.

**React to new events, read anything that comes to you over the web, never reach
into another app.**
