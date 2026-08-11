// Variables used by Scriptable.
// icon-color: teal; icon-glyph: stethoscope;
//
// Scriptable self-test — run this ON the iPad before trusting job_watcher.js.
//
// It answers the two questions I could not answer from a Linux container:
// does this Scriptable build have the APIs the watcher needs, and what do the
// job feeds actually return? For each feed it prints the REAL field names, so
// a wrong mapping in job_watcher.js becomes a copy-paste fix.
//
// Read-only. Writes one small file to test that writing works, then deletes it.
// Sends nothing anywhere. The report is copied to your clipboard at the end.

const FEEDS = [
  { name: "Remotive", type: "json", url: "https://remotive.com/api/remote-jobs", list: "jobs" },
  { name: "Arbeitnow", type: "json", url: "https://www.arbeitnow.com/api/job-board-api", list: "data" },
  { name: "WeWorkRemotely", type: "rss", url: "https://weworkremotely.com/remote-jobs.rss" },
];

const lines = [];
function out(text) {
  lines.push(text);
  console.log(text);
}

out("Scriptable self-test");
out("=".repeat(34));

// --- device ----------------------------------------------------------------

try {
  out("Device:     " + Device.model() + ", " + Device.systemName() + " " + Device.systemVersion());
} catch (err) {
  out("Device:     could not read (" + err + ")");
}

// --- APIs the watcher depends on -------------------------------------------

out("");
out("APIs");
const NEEDED = ["Request", "XMLParser", "FileManager", "Notification",
                "ListWidget", "UITable", "UITableRow", "Pasteboard", "Safari", "Script"];
let missing = 0;
NEEDED.forEach((name) => {
  const present = typeof globalThis[name] !== "undefined";
  if (!present) missing += 1;
  out("  " + (present ? "ok      " : "MISSING ") + name);
});

// --- can it store state? ---------------------------------------------------

out("");
out("Storage");
try {
  const fm = FileManager.local();
  const path = fm.joinPath(fm.documentsDirectory(), "selftest_probe.txt");
  fm.writeString(path, "probe");
  const readBack = fm.readString(path) === "probe";
  out("  " + (readBack ? "ok      " : "FAILED  ") + "write and read back");
  try { fm.remove(path); } catch (err) { /* leaving a 5-byte file is harmless */ }
} catch (err) {
  out("  FAILED  storage: " + err);
  missing += 1;
}

// --- feeds -----------------------------------------------------------------

function keysOf(object) {
  if (!object || typeof object !== "object") return "(not an object)";
  return Object.keys(object).join(", ");
}

async function probeJson(feed) {
  const started = Date.now();
  const request = new Request(feed.url);
  request.timeoutInterval = 25;
  const payload = await request.loadJSON();
  const elapsed = Date.now() - started;

  out("  reached in " + elapsed + "ms");
  out("  top-level keys: " + keysOf(payload));

  const rows = feed.list ? payload[feed.list] : payload;
  if (!Array.isArray(rows)) {
    out('  PROBLEM: expected a list at "' + feed.list + '" but found ' + typeof rows);
    return;
  }
  out("  " + rows.length + " row(s) under \"" + feed.list + "\"");

  const sample = rows.find((row) => row && typeof row === "object");
  if (!sample) {
    out("  PROBLEM: no usable rows");
    return;
  }
  out("  FIELD NAMES: " + keysOf(sample));
  ["title", "company_name", "url", "publication_date", "created_at"].forEach((field) => {
    if (field in sample) {
      out('    "' + field + '" = ' + String(sample[field]).slice(0, 60));
    }
  });
}

async function probeRss(feed) {
  const started = Date.now();
  const request = new Request(feed.url);
  request.timeoutInterval = 25;
  const xml = await request.loadString();
  out("  reached in " + (Date.now() - started) + "ms, " + xml.length + " chars");

  let items = 0;
  let firstTitle = "";
  let inItem = false;
  let element = null;
  const parser = new XMLParser(xml);
  parser.didStartElement = (name) => {
    element = name;
    if (name === "item" || name === "entry") { inItem = true; items += 1; }
  };
  parser.foundCharacters = (text) => {
    if (inItem && element === "title" && !firstTitle) firstTitle = text;
  };
  parser.didEndElement = (name) => {
    if (name === "item" || name === "entry") inItem = false;
    element = null;
  };
  parser.parse();

  out("  " + items + " item(s) parsed");
  if (items) out("  first title: " + firstTitle.trim().slice(0, 70));
  else out("  PROBLEM: XMLParser found no <item> elements");
}

out("");
out("Feeds");
for (const feed of FEEDS) {
  out("");
  out(feed.name + "  (" + feed.type + ")");
  try {
    if (feed.type === "rss") await probeRss(feed);
    else await probeJson(feed);
  } catch (err) {
    out("  UNREACHABLE: " + err);
  }
}

// --- verdict ---------------------------------------------------------------

out("");
out("=".repeat(34));
out(missing === 0
  ? "APIs all present. Check each feed above for PROBLEM or UNREACHABLE."
  : missing + " required API(s) missing — job_watcher.js will not run properly.");
out("");
out("If a feed's FIELD NAMES differ from what job_watcher.js expects,");
out("copy them into that feed's `fields` block and it will work.");

try {
  Pasteboard.copy(lines.join("\n"));
  out("");
  out("(This report is now on your clipboard — paste it back to share it.)");
} catch (err) {
  // Not fatal; the console output above is the report.
}

if (typeof QuickLook !== "undefined") {
  await QuickLook.present(lines.join("\n"), false);
}

Script.complete();
