# iPad agents

Small automations that run on the iPad itself. Nothing here needs an API key, a
paid service, or an account beyond what you already have.

| What | How it ships | Needs |
|---|---|---|
| [Job feed watcher](job_watcher.js) | JavaScript file | Scriptable (free) |
| [Job alerts from LinkedIn email](SHORTCUTS.md#1-job-alerts-from-linkedin-without-touching-linkedin) | build steps | Shortcuts (built in) |
| [Message triage](SHORTCUTS.md#2-message-triage) | build steps | Shortcuts (built in) |
| [Storage cleanup](SHORTCUTS.md#3-storage-cleanup) | build steps | Shortcuts (built in) |
| [Photo duplicate finder](../photo-dedupe/) | Python file | Pythonista (paid) |

## What decides whether something is possible on iPad

Worth understanding, because it is not about cleverness.

Every iPad app runs in a sandbox and can only reach data Apple built a bridge
for. Apple built bridges for Photos, Calendar, Reminders, Contacts, Health,
Files, Location, the clipboard, notifications and web requests. Everything in
this folder sits on one of those bridges.

Apple built no bridge for your Messages history, other apps' internal data, or
controlling another app's screen. No app can reach those — not these scripts,
not a paid one. When something here says "not possible," that is the operating
system, not a missing feature.

The practical version of that rule: **you can react to new events, and you can
read anything that comes to you over the web. You cannot reach into another
app.**

## Job feed watcher

`job_watcher.js` checks public job feeds, keeps the postings matching your
keywords, and tells you about anything new since it last ran.

1. Install [Scriptable](https://scriptable.app) (free).
2. Open it → **+** → paste the file in → name it `Job watcher`.
3. Edit the block at the top: `KEYWORDS` for what you want, `EXCLUDE` for what
   you don't.
4. Tap it to run. You get a scrollable list; tapping a job opens it.

Add it as a home screen widget: long-press the home screen → **+** → Scriptable
→ choose `Job watcher` as the script. Or run it on a schedule with a **Time of
Day** automation in Shortcuts pointed at **Run Script**.

It remembers what it has already shown you in
`job_watcher_seen.json`, so the "new" count means genuinely new.

### About the feeds

The default feeds are public endpoints that job boards publish for this purpose
— Remotive, Arbeitnow and We Work Remotely. This is not scraping and does not
violate anyone's terms.

**I could not reach those endpoints to verify their exact field names**, because
this build environment blocks outbound access to them. The JSON mappings are
written from knowledge of those APIs, not from a live response, so one may be
wrong.

Rather than let that fail silently, the script diagnoses itself. If a feed
returns data but no usable jobs, the console prints the real field names:

```
WARN Arbeitnow: got 1 row(s) but no titles under "title".
     Actual fields: position, firm, href
```

Copy those names into that feed's `fields` block and it works. If a feed is
dead, it is skipped and the others still run.

Adding your own feed is the easy path: most job boards publish RSS, and an RSS
entry needs no field mapping at all — just the URL with `type: "rss"`.

## LinkedIn, honestly

I cannot automate your LinkedIn account, and neither can anything else on an
iPad. Two separate reasons:

- LinkedIn's User Agreement prohibits automated access. Accounts that do it get
  restricted.
- iPadOS cannot drive a logged-in browser session anyway. There is no Selenium
  on iOS.

The route that does work is to invert it: **let LinkedIn send data to you.**
Turn on job alert emails, then have Shortcuts react when one arrives. You get
the listings automatically, with no risk to your account. That is section 1 of
[SHORTCUTS.md](SHORTCUTS.md).

The same inversion works generally. Anything that will email you, RSS you, or
publish a public feed can be automated on an iPad. Anything that requires
logging in and clicking around cannot.

## Testing status

`job_watcher.js` has its parsing, keyword matching, cross-feed deduplication,
state persistence and field diagnostics tested against a stubbed Scriptable
runtime with fixture feeds. Confirmed working: the same job appearing in two
feeds is counted once, `EXCLUDE` drops matches the keywords caught, and a second
run reports zero new without re-notifying.

Not tested: live network calls (blocked here) and Scriptable's real widget and
table rendering. Also worth knowing — Scriptable is free but has reports of
instability on recent iOS versions. Try it before depending on it; it costs
nothing to find out.

The Shortcuts builds are written from Apple's documented triggers and actions.
They have not been built on a device. The Email and Message triggers in
particular are historically unreliable — test each one before trusting it.
