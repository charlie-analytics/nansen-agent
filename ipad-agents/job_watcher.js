// Variables used by Scriptable.
// icon-color: blue; icon-glyph: briefcase;
//
// Job watcher — checks public job feeds, keeps the ones matching your
// keywords, and tells you about anything new since the last run.
//
// Runs three ways:
//   * tapped in Scriptable  -> full list you can scroll and tap through
//   * as a home screen widget -> newest matches at a glance
//   * from a Shortcuts automation -> silent check + notification
//
// No API keys, no accounts, no scraping. Every feed below is a public
// endpoint the site publishes for this purpose.

// ---------------------------------------------------------------------------
// EDIT THIS PART
// ---------------------------------------------------------------------------

// A job matches if its title contains ANY of these. Lowercase.
const KEYWORDS = ["python", "data analyst", "data engineer", "backend"];

// ...and NONE of these. Use it to drop levels or roles you don't want.
const EXCLUDE = ["senior staff", "principal", "director", "unpaid"];

// Set to false once you trust it, to stop the notifications.
const NOTIFY = true;

// How many jobs the widget shows.
const WIDGET_ROWS = 4;

// Feeds. Comment out any you don't care about, or add your own —
// most job boards publish an RSS feed, which "rss" handles generically.
const FEEDS = [
  {
    name: "Remotive",
    type: "json",
    url: "https://remotive.com/api/remote-jobs",
    list: "jobs",
    fields: { title: "title", company: "company_name", url: "url", date: "publication_date" },
  },
  {
    name: "Arbeitnow",
    type: "json",
    url: "https://www.arbeitnow.com/api/job-board-api",
    list: "data",
    fields: { title: "title", company: "company_name", url: "url", date: "created_at" },
  },
  {
    name: "WeWorkRemotely",
    type: "rss",
    url: "https://weworkremotely.com/remote-jobs.rss",
  },
  // Add your own: almost every job board publishes RSS. Find its feed URL and
  // paste it in with type "rss" — no field mapping needed.
];

// ---------------------------------------------------------------------------
// Below here you should not need to change anything.
// ---------------------------------------------------------------------------

const STATE_FILE = "job_watcher_seen.json";
const MAX_REMEMBERED = 800;

// --- storage ---------------------------------------------------------------

function statePath() {
  const fm = FileManager.local();
  return fm.joinPath(fm.documentsDirectory(), STATE_FILE);
}

function loadSeen() {
  try {
    const fm = FileManager.local();
    const path = statePath();
    if (!fm.fileExists(path)) return [];
    const parsed = JSON.parse(fm.readString(path));
    return Array.isArray(parsed) ? parsed : [];
  } catch (err) {
    // A corrupt state file must not stop the run — worst case is one
    // round of duplicate notifications.
    return [];
  }
}

function saveSeen(ids) {
  try {
    const trimmed = ids.slice(-MAX_REMEMBERED);
    FileManager.local().writeString(statePath(), JSON.stringify(trimmed));
  } catch (err) {
    console.warn("Could not save state: " + err);
  }
}

// --- fetching --------------------------------------------------------------

function textOf(value) {
  if (value === null || value === undefined) return "";
  return String(value);
}

function stripTags(html) {
  return textOf(html)
    .replace(/<[^>]*>/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#x27;|&#39;/g, "'")
    .replace(/&nbsp;/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

async function fetchJson(feed) {
  const request = new Request(feed.url);
  request.timeoutInterval = 20;
  const payload = await request.loadJSON();

  let rows = feed.list ? payload[feed.list] : payload;
  if (!Array.isArray(rows)) {
    console.warn(
      feed.name + ': expected a list at "' + feed.list + '". Top-level keys are: ' +
        Object.keys(payload || {}).join(", ")
    );
    return [];
  }

  const map = feed.fields || {};
  const jobs = rows
    .map((row) => {
      if (!row || typeof row !== "object") return null;
      return {
        title: stripTags(row[map.title]),
        company: stripTags(row[map.company]) || feed.name,
        url: textOf(row[map.url]),
        date: textOf(row[map.date]),
        source: feed.name,
      };
    })
    .filter((job) => job && job.title);

  // A feed that returns rows but no usable jobs means the field names below
  // are wrong for this endpoint. Say so loudly, with the real key names, so
  // it can be fixed in seconds instead of looking like "no jobs today".
  if (rows.length && !jobs.length) {
    const sample = rows.find((row) => row && typeof row === "object");
    console.warn(
      feed.name + ': got ' + rows.length + ' row(s) but no titles under "' +
        map.title + '". Actual fields: ' + (sample ? Object.keys(sample).join(", ") : "none")
    );
  }
  return jobs;
}

async function fetchRss(feed) {
  const request = new Request(feed.url);
  request.timeoutInterval = 20;
  const xml = await request.loadString();

  const jobs = [];
  let current = null;
  let element = null;

  const parser = new XMLParser(xml);
  parser.didStartElement = (name) => {
    element = name;
    // <item> is RSS, <entry> is Atom — accept both.
    if (name === "item" || name === "entry") current = { title: "", url: "", date: "" };
  };
  parser.foundCharacters = (text) => {
    if (!current || !element) return;
    if (element === "title") current.title += text;
    else if (element === "link") current.url += text;
    else if (element === "pubDate" || element === "updated" || element === "published") {
      current.date += text;
    }
  };
  parser.didEndElement = (name) => {
    if ((name === "item" || name === "entry") && current) {
      const title = stripTags(current.title);
      if (title) {
        // Feeds commonly pack "Company: Role" into the title; split when we can
        // so the company shows separately, but never lose the original text.
        const split = title.split(":");
        const hasCompany = split.length > 1 && split[0].length < 40;
        jobs.push({
          title: hasCompany ? split.slice(1).join(":").trim() : title,
          company: hasCompany ? split[0].trim() : feed.name,
          url: current.url.trim(),
          date: current.date.trim(),
          source: feed.name,
        });
      }
      current = null;
    }
    element = null;
  };
  parser.parse();
  return jobs;
}

async function fetchFeed(feed) {
  try {
    const jobs = feed.type === "rss" ? await fetchRss(feed) : await fetchJson(feed);
    console.log(feed.name + ": " + jobs.length + " job(s)");
    return jobs;
  } catch (err) {
    // One dead feed should never take the whole run down.
    console.warn(feed.name + " failed: " + err);
    return [];
  }
}

// --- matching --------------------------------------------------------------

function matches(job) {
  const haystack = (job.title + " " + job.company).toLowerCase();
  if (KEYWORDS.length && !KEYWORDS.some((word) => haystack.includes(word.toLowerCase()))) {
    return false;
  }
  return !EXCLUDE.some((word) => word && haystack.includes(word.toLowerCase()));
}

function identify(job) {
  // URL is the stable identity; fall back to the text when a feed omits it.
  return job.url ? job.url : job.source + "|" + job.title + "|" + job.company;
}

function shorten(text, limit) {
  const clean = textOf(text).trim();
  return clean.length <= limit ? clean : clean.slice(0, limit - 1).trim() + "…";
}

// --- output ----------------------------------------------------------------

function buildWidget(jobs, freshCount) {
  const widget = new ListWidget();
  widget.setPadding(12, 14, 12, 14);

  const header = widget.addText(
    freshCount > 0 ? freshCount + " new job" + (freshCount === 1 ? "" : "s") : "Jobs"
  );
  header.font = Font.semiboldSystemFont(13);
  header.textColor = freshCount > 0 ? Color.blue() : Color.gray();
  widget.addSpacer(6);

  if (!jobs.length) {
    const empty = widget.addText("No matches right now.");
    empty.font = Font.systemFont(12);
    empty.textColor = Color.gray();
  } else {
    jobs.slice(0, WIDGET_ROWS).forEach((job, index) => {
      if (index) widget.addSpacer(5);
      const title = widget.addText(shorten(job.title, 46));
      title.font = Font.systemFont(12);
      const company = widget.addText(shorten(job.company + " · " + job.source, 40));
      company.font = Font.systemFont(10);
      company.textColor = Color.gray();
    });
  }

  widget.addSpacer();
  const stamp = widget.addText("Updated " + new Date().toLocaleTimeString());
  stamp.font = Font.systemFont(9);
  stamp.textColor = Color.gray();

  // Ask iOS to refresh in about an hour. It treats this as a hint, not a promise.
  widget.refreshAfterDate = new Date(Date.now() + 60 * 60 * 1000);
  return widget;
}

async function presentTable(jobs) {
  const table = new UITable();
  table.showSeparators = true;

  if (!jobs.length) {
    const row = new UITableRow();
    row.addText("No matches", "Loosen KEYWORDS at the top of the script.");
    table.addRow(row);
  }

  jobs.forEach((job) => {
    const row = new UITableRow();
    row.height = 62;
    row.dismissOnSelect = false;
    row.addText(shorten(job.title, 70), job.company + " · " + job.source);
    if (job.url) {
      row.onSelect = () => Safari.open(job.url);
    }
    table.addRow(row);
  });

  await table.present();
}

function notify(fresh) {
  if (!NOTIFY || !fresh.length) return;
  const notification = new Notification();
  notification.title = fresh.length + " new job match" + (fresh.length === 1 ? "" : "es");
  notification.body = fresh
    .slice(0, 3)
    .map((job) => job.title)
    .join("\n");
  notification.sound = "default";
  notification.schedule();
}

// --- main ------------------------------------------------------------------

async function run() {
  const batches = await Promise.all(FEEDS.map(fetchFeed));

  const byId = new Map();
  batches.forEach((batch) => {
    batch.filter(matches).forEach((job) => {
      // Same job often appears on several boards; first sighting wins.
      const id = identify(job);
      if (!byId.has(id)) byId.set(id, job);
    });
  });

  const jobs = Array.from(byId.values());
  jobs.sort((a, b) => {
    const left = Date.parse(b.date) || 0;
    const right = Date.parse(a.date) || 0;
    return left - right;
  });

  const seen = loadSeen();
  const seenSet = new Set(seen);
  const fresh = jobs.filter((job) => !seenSet.has(identify(job)));

  console.log(jobs.length + " matching, " + fresh.length + " new");
  saveSeen(seen.concat(fresh.map(identify)));

  if (config.runsInWidget) {
    Script.setWidget(buildWidget(fresh.length ? fresh : jobs, fresh.length));
  } else if (config.runsInApp) {
    notify(fresh);
    await presentTable(jobs);
  } else {
    // Launched by Shortcuts, Siri or an automation: stay silent apart from
    // the notification, and hand the count back to the caller.
    notify(fresh);
    Script.setShortcutOutput(fresh.length + " new / " + jobs.length + " matching");
  }

  Script.complete();
}

await run();
