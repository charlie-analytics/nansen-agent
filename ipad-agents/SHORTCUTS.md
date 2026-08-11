# Shortcuts to build on the iPad

Three automations, built in the Shortcuts app that is already installed. No
downloads, no accounts, no API keys.

I cannot hand you these as files — a `.shortcut` file has to be signed by the
device that made it, and I have no iPad. These are build steps instead. Each
takes a few minutes.

A general note before you start: **the Email and Message triggers are the least
reliable part of Shortcuts.** Apple has had long-standing bugs where they fire
late or not at all. Build the job-alert one first and give it a day before you
trust it with anything that matters.

---

## 1. Job alerts from LinkedIn, without touching LinkedIn

The idea: LinkedIn already emails you jobs. Let the iPad react to that email.
Nothing automates your account, so nothing puts it at risk.

**First, on LinkedIn (once):**

1. Search for the job you want, then turn on the **Job Alert** toggle.
2. Set it to **Daily** email.
3. Note the sender address of the first alert that arrives — usually
   `jobalerts-noreply@linkedin.com`. Use whatever yours actually says.

**Then, in Shortcuts:**

1. Open **Shortcuts** → **Automation** tab → **+** (top right).
2. Scroll to **Email**.
3. Set the filters — these do the real work, so be specific:
   - **Sender**: the LinkedIn alert address from step 3 above.
   - **Subject Contains**: a keyword from your search, e.g. `data analyst`.
     Leave blank to catch every alert.
4. Choose **Run Immediately**. (iOS will still notify you when it runs — that
   is forced for communication triggers and cannot be turned off.)
5. **Next** → **New Blank Automation**.
6. Add these actions in order:
   - **Show Notification** — text: `New job alert matched`.
   - **Append to Note** — pick a note called `Job alerts`, append `Shortcut
     Input` and the **Current Date**.
7. **Done**.

Now every matching alert gets logged into one note, and you get a single ping
instead of digging through mail.

**Optional, if your iOS version exposes the email body:** insert **Get Text from
Input** before the append step, then **Match Text** with a pattern like
`(?i)(remote|hybrid)` to keep only the ones you care about. If the email content
comes through blank, your iOS build does not pass the body to the automation —
drop back to filtering with the trigger's own **Subject Contains** field, which
always works.

---

## 2. Message triage

Reacts to messages **as they arrive**. It cannot read your message history —
nothing on iOS can.

1. **Shortcuts** → **Automation** → **+** → **Message**.
2. Set either or both:
   - **Sender**: the people who matter.
   - **Message Contains**: words like `urgent`, `invoice`, `interview`.
3. **Run Immediately** → **Next** → **New Blank Automation**.
4. Pick one of these shapes:

   **Just flag it** (safe, recommended to start):
   - **Show Notification**, text `Important message`, sound on.

   **Log it for later**:
   - **Append to Note** → note `Flagged messages` → append `Shortcut Input`.

   **Auto-reply** (be careful):
   - **Send Message** → recipient `Shortcut Input`, text
     `Got it — I'll reply properly this evening.`

On auto-reply: it sends without showing you first. Restrict it to a specific
sender, and test it on your own second device or a friend before letting it
loose. A wrong auto-reply to the wrong person is not something you can recall.

---

## 3. Storage cleanup

Pure Shortcuts, no triggers involved, so this one is reliable.

**Old screenshots:**

1. **Shortcuts** → **Shortcuts** tab → **+**.
2. Add **Find Photos Where**:
   - `Album` `is` `Screenshots`
   - tap **+** → `Date Taken` `is not in the last` `30` `days`
   - **Sort by** `Date Taken`, **Order** `Oldest First`
   - **Limit** `50` — a cap keeps the first run from being alarming.
3. Add **Delete Photos**, input `Photos` from the step above.
4. Name it `Clear old screenshots`. **Done**.

Run it by hand a few times first. Deleted photos go to **Recently Deleted** and
stay recoverable for 30 days.

By default iOS asks for confirmation before the delete. Keep that on until you
trust it. If you later want it silent: **Settings → Shortcuts → Advanced →
Allow Deleting Without Confirmation.** Think twice — that switch applies to
every shortcut you run, not just this one.

**To make it automatic:** **Automation** → **+** → **Time of Day** → Weekly,
Sunday 9pm → run `Clear old screenshots`. Note that a scheduled run cannot ask
for confirmation, so it needs the setting above turned on. I would leave this
one manual.

**Large files in iCloud Drive:** new shortcut → **Get File** (pick a folder,
turn on *Select Multiple*) → **Filter Files** where `File Size` `is greater
than` `100 MB` → **Quick Look**. It shows you what is big; it does not delete
anything.

---

## What none of these can do

Not limitations of the instructions — limitations of iOS itself:

- Read your existing messages or emails. Only react to new ones.
- Open, read, or control another app such as LinkedIn, WhatsApp or Instagram.
- Run continuously in the background. Automations fire on their trigger, then
  stop.
- Apply to jobs for you. Nothing on iPadOS can drive a website's forms.
