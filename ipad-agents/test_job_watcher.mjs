// Test suite for job_watcher.js.
//
//     node test_job_watcher.mjs
//
// Stubs Scriptable's runtime (Request, XMLParser, FileManager, Notification,
// widgets) so the script can run off-device with fixture feeds instead of live
// network calls. Exits non-zero if any check fails.

const passed = [];
const failed = [];

function check(label, condition, detail = "") {
  if (condition) {
    passed.push(label);
    process.stdout.write("  PASS  " + label + "\n");
  } else {
    failed.push(label);
    process.stdout.write("  FAIL  " + label + (detail ? " -- " + detail : "") + "\n");
  }
}

function section(title) {
  process.stdout.write("\n" + title + "\n" + "-".repeat(title.length) + "\n");
}

// --- fixtures --------------------------------------------------------------

const RSS = `<?xml version="1.0"?>
<rss><channel>
<title>We Work Remotely</title>
<item><title>Acme Corp: Backend Engineer</title><link>https://ex.com/a</link><pubDate>Mon, 10 Aug 2026 10:00:00 GMT</pubDate></item>
<item><title>Globex: Principal Data Engineer</title><link>https://ex.com/b</link><pubDate>Tue, 11 Aug 2026 09:00:00 GMT</pubDate></item>
<item><title>Initech: Marketing Lead</title><link>https://ex.com/c</link><pubDate>Tue, 11 Aug 2026 08:00:00 GMT</pubDate></item>
</channel></rss>`;

// Same job as the RSS feed's first item, same URL, to prove cross-feed dedup.
const REMOTIVE = {
  jobs: [
    { title: "Python Developer", company_name: "Umbrella", url: "https://ex.com/d", publication_date: "2026-08-11T12:00:00" },
    { title: "Chef", company_name: "Bistro", url: "https://ex.com/e", publication_date: "2026-08-11T11:00:00" },
    { title: "Backend Engineer", company_name: "Acme Corp", url: "https://ex.com/a", publication_date: "2026-08-10T10:00:00" },
  ],
};

// Deliberately wrong field names, to prove the mapping diagnostic fires.
const ARBEITNOW = { data: [{ position: "Data Analyst", firm: "Soylent", href: "https://ex.com/f" }] };

// --- Scriptable runtime stubs ----------------------------------------------

let logs = [];
globalThis.console = { log: (m) => logs.push(String(m)), warn: (m) => logs.push("WARN " + m) };

let failFeeds = new Set();

globalThis.Request = class {
  constructor(url) { this.url = url; }
  async loadJSON() {
    if (failFeeds.has("json")) throw new Error("simulated network failure");
    if (this.url.includes("remotive")) return REMOTIVE;
    if (this.url.includes("arbeitnow")) return ARBEITNOW;
    throw new Error("unreachable host");
  }
  async loadString() {
    if (failFeeds.has("rss")) throw new Error("simulated network failure");
    if (this.url.includes("weworkremotely")) return RSS;
    throw new Error("unreachable host");
  }
};

globalThis.XMLParser = class {
  constructor(text) { this.text = text; }
  parse() {
    const pattern = /<(\/?)([A-Za-z0-9_:-]+)[^>]*>([^<]*)/g;
    let match;
    while ((match = pattern.exec(this.text))) {
      const [, slash, name, text] = match;
      if (slash) {
        if (this.didEndElement) this.didEndElement(name);
      } else {
        if (this.didStartElement) this.didStartElement(name, {});
        if (text && this.foundCharacters) this.foundCharacters(text);
      }
    }
    return true;
  }
};

const store = new Map();
globalThis.FileManager = {
  local: () => ({
    documentsDirectory: () => "/docs",
    joinPath: (a, b) => a + "/" + b,
    fileExists: (p) => store.has(p),
    readString: (p) => store.get(p),
    writeString: (p, v) => store.set(p, v),
    remove: (p) => store.delete(p),
  }),
};

let notifications = [];
globalThis.Notification = class {
  schedule() { notifications.push({ title: this.title, body: this.body }); }
};

globalThis.Color = { blue: () => "blue", gray: () => "gray" };
globalThis.Font = { semiboldSystemFont: () => "f", systemFont: () => "f" };
globalThis.Safari = { open: () => {} };
globalThis.ListWidget = class {
  constructor() { this.texts = []; }
  setPadding() {}
  addSpacer() {}
  addText(t) { this.texts.push(t); return {}; }
};
globalThis.UITable = class { constructor() { this.rows = []; } addRow(r) { this.rows.push(r); } async present() {} };
globalThis.UITableRow = class { constructor() { this.cells = []; } addText(a, b) { this.cells.push([a, b]); } };

let output = null;
globalThis.config = { runsInWidget: false, runsInApp: false };
globalThis.Script = {
  setWidget: (w) => { output = w; },
  setShortcutOutput: (v) => { output = v; },
  complete: () => {},
};

let runCount = 0;
async function runScript() {
  logs = [];
  notifications = [];
  output = null;
  runCount += 1;
  // Cache-bust so each run re-executes the module body.
  await import("./job_watcher.js?run=" + runCount);
  return { logs: logs.join("\n"), notifications, output };
}

// --- tests -----------------------------------------------------------------

process.stdout.write("Job watcher test suite\n" + "=".repeat(40) + "\n");
process.stdout.write(
  "Fixtures: 3 feeds, 7 postings, 2 of which match the default keywords.\n" +
  "One feed has deliberately wrong field names.\n");

section("First run, cold state");
let r = await runScript();
process.stdout.write("  console output:\n");
r.logs.split("\n").forEach((l) => process.stdout.write("    | " + l + "\n"));

check("parses the RSS feed", r.logs.includes("WeWorkRemotely: 3 job(s)"));
check("parses the JSON feed", r.logs.includes("Remotive: 3 job(s)"));
check("matches 2 jobs", r.logs.includes("2 matching"), r.logs);
check("deduplicates the job shared by two feeds",
  r.logs.includes("2 matching") && !r.logs.includes("3 matching"));
check("EXCLUDE drops 'Principal Data Engineer'", !JSON.stringify(r.notifications).includes("Principal"));
check("keyword filter drops unrelated jobs",
  !JSON.stringify(r.notifications).includes("Chef") &&
  !JSON.stringify(r.notifications).includes("Marketing"));
check("reports both new jobs", r.logs.includes("2 new"));
check("sends one notification", r.notifications.length === 1, JSON.stringify(r.notifications));
check("notification names the jobs",
  r.notifications[0] && r.notifications[0].body.includes("Python Developer"));
check("hands a summary back to Shortcuts", output === "2 new / 2 matching", String(output));

section("Bad field mapping diagnoses itself");
check("warns instead of failing silently", r.logs.includes("Arbeitnow: got 1 row(s) but no titles"));
check("prints the real field names", r.logs.includes("position, firm, href"),
  "diagnostic should name the actual keys");
check("a broken feed does not stop the others", r.logs.includes("Remotive: 3 job(s)"));

section("Second run, state remembered");
r = await runScript();
r.logs.split("\n").forEach((l) => process.stdout.write("    | " + l + "\n"));
check("still matches the same 2 jobs", r.logs.includes("2 matching"));
check("reports 0 new", r.logs.includes("0 new"), r.logs);
check("does not re-notify", r.notifications.length === 0, JSON.stringify(r.notifications));
check("persisted state to disk", store.has("/docs/job_watcher_seen.json"));
check("state holds both job ids",
  JSON.parse(store.get("/docs/job_watcher_seen.json")).length === 2,
  store.get("/docs/job_watcher_seen.json"));

section("Widget rendering");
globalThis.config = { runsInWidget: true, runsInApp: false };
r = await runScript();
check("builds a widget", output && Array.isArray(output.texts), typeof output);
check("widget shows a heading and rows", output.texts.length > 1, JSON.stringify(output.texts));
check("widget says 'Jobs' when nothing is new",
  output.texts[0] === "Jobs", JSON.stringify(output.texts[0]));
globalThis.config = { runsInWidget: false, runsInApp: false };

section("Every feed offline");
failFeeds = new Set(["json", "rss"]);
store.clear();
r = await runScript();
r.logs.split("\n").forEach((l) => process.stdout.write("    | " + l + "\n"));
check("survives total network failure", r.logs.includes("0 matching"), r.logs);
check("reports each failure", (r.logs.match(/failed:/g) || []).length === 3, r.logs);
check("sends no notification when there is nothing", r.notifications.length === 0);
failFeeds = new Set();

section("selftest.js -- the on-device capability check");
globalThis.Device = {
  model: () => "iPad Pro", systemName: () => "iPadOS", systemVersion: () => "18.5",
};
let clipboard = null;
globalThis.Pasteboard = { copy: (text) => { clipboard = text; } };
const probeStore = store;
await import("./selftest.js?run=1");

check("names the device", clipboard.includes("iPad Pro, iPadOS 18.5"), String(clipboard).slice(0, 80));
check("checks every API the watcher needs",
  clipboard.includes("ok      Request") && clipboard.includes("ok      XMLParser"));
check("verifies storage works", clipboard.includes("ok      write and read back"));
check("reports a reachable feed's real field names",
  clipboard.includes("FIELD NAMES: title, company_name, url, publication_date"),
  String(clipboard));
check("reports the mis-mapped feed's actual fields",
  clipboard.includes("FIELD NAMES: position, firm, href"));
check("parses the RSS feed", clipboard.includes("item(s) parsed"));
check("cleans up its probe file", !probeStore.has("/docs/selftest_probe.txt"));
check("copies the report to the clipboard", clipboard.length > 200);

// --- summary ---------------------------------------------------------------

process.stdout.write("\n" + "=".repeat(40) + "\n");
process.stdout.write(passed.length + " passed, " + failed.length + " failed\n");
if (failed.length) {
  failed.forEach((l) => process.stdout.write("  FAILED: " + l + "\n"));
  process.exit(1);
}
