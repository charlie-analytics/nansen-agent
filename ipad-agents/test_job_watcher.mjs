// Stubs Scriptable's runtime so job_watcher.js can be exercised off-device.
// Verifies feed parsing, keyword matching, cross-feed dedup, state persistence
// and the diagnostic that fires when a feed's field mapping is wrong.

const RSS = `<?xml version="1.0"?>
<rss><channel>
<title>We Work Remotely</title>
<item><title>Acme Corp: Backend Engineer</title><link>https://ex.com/a</link><pubDate>Mon, 10 Aug 2026 10:00:00 GMT</pubDate></item>
<item><title>Globex: Principal Data Engineer</title><link>https://ex.com/b</link><pubDate>Tue, 11 Aug 2026 09:00:00 GMT</pubDate></item>
<item><title>Initech: Marketing Lead</title><link>https://ex.com/c</link><pubDate>Tue, 11 Aug 2026 08:00:00 GMT</pubDate></item>
</channel></rss>`;

const REMOTIVE = {
  jobs: [
    { title: "Python Developer", company_name: "Umbrella", url: "https://ex.com/d", publication_date: "2026-08-11T12:00:00" },
    { title: "Chef", company_name: "Bistro", url: "https://ex.com/e", publication_date: "2026-08-11T11:00:00" },
    { title: "Backend Engineer", company_name: "Acme Corp", url: "https://ex.com/a", publication_date: "2026-08-10T10:00:00" },
  ],
};

// Deliberately wrong field names, to prove the diagnostic fires.
const ARBEITNOW = { data: [{ position: "Data Analyst", firm: "Soylent", href: "https://ex.com/f" }] };

const logs = [];
globalThis.console = { log: (m) => logs.push("LOG " + m), warn: (m) => logs.push("WARN " + m) };

globalThis.Request = class {
  constructor(url) { this.url = url; }
  async loadJSON() {
    if (this.url.includes("remotive")) return REMOTIVE;
    if (this.url.includes("arbeitnow")) return ARBEITNOW;
    throw new Error("unreachable host");
  }
  async loadString() {
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
      if (slash) { this.didEndElement && this.didEndElement(name); }
      else {
        this.didStartElement && this.didStartElement(name, {});
        if (text) this.foundCharacters && this.foundCharacters(text);
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
  }),
};

const notifications = [];
globalThis.Notification = class {
  schedule() { notifications.push({ title: this.title, body: this.body }); }
};

globalThis.Color = { blue: () => "blue", gray: () => "gray" };
globalThis.Font = { semiboldSystemFont: () => "f", systemFont: () => "f" };
globalThis.Safari = { open: () => {} };
globalThis.ListWidget = class {
  constructor() { this.texts = []; }
  setPadding() {} addSpacer() {}
  addText(t) { this.texts.push(t); return {}; }
};
globalThis.UITable = class { addRow() {} async present() {} };
globalThis.UITableRow = class { addText() {} };

let output = null;
globalThis.config = { runsInWidget: false, runsInApp: false };
globalThis.Script = {
  setWidget: (w) => { output = w; },
  setShortcutOutput: (v) => { output = v; },
  complete: () => {},
};

console.log("--- run 1 (cold state) ---");
await import("./job_watcher.js");
logs.splice(0).forEach((l) => process.stdout.write(l + "\n"));
process.stdout.write("output: " + output + "\n");
process.stdout.write("notified: " + JSON.stringify(notifications) + "\n");

process.stdout.write("\n--- run 2 (same feeds, state warm) ---\n");
notifications.length = 0;
const again = await import("./job_watcher.js?v=2");
logs.splice(0).forEach((l) => process.stdout.write(l + "\n"));
process.stdout.write("output: " + output + "\n");
process.stdout.write("notified: " + JSON.stringify(notifications) + "\n");
process.stdout.write("\nstate file: " + store.get("/docs/job_watcher_seen.json") + "\n");
