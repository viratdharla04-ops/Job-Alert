# SAP Security / GRC Job Alert Bot

Runs daily on GitHub Actions (free) and emails you new SAP Security/GRC job
postings (full-time and contract, all companies, any location) to
viratdharla04@gmail.com.

**Filter logic:** shows a job if it lists 4+ years experience, OR lists
under 4 years but pays $120K+, OR doesn't mention experience at all (shown
so nothing potentially relevant is hidden — flagged in the email so you can
tell at a glance).

## One-time setup (about 10 minutes)

### 1. Get a free Adzuna API key
1. Go to https://developer.adzuna.com and register (free, no card needed).
2. Copy your **App ID** and **App Key** from the dashboard.

### 2. Create a Gmail App Password
Gmail won't accept your normal password for automated sending.
1. Turn on 2-Step Verification on your Google account (if not already on):
   https://myaccount.google.com/security
2. Go to https://myaccount.google.com/apppasswords
3. Create an app password (name it e.g. "job-bot") and copy the 16-character
   code it gives you.

### 3. Create a GitHub repo
1. Go to https://github.com/new, create a new **private** repo (e.g.
   `sap-job-bot`).
2. Upload all the files from this folder into it (drag-and-drop on the
   GitHub web UI works fine, or use `git push` if you're comfortable with
   git).

### 4. Add your secrets
In your new repo: **Settings → Secrets and variables → Actions → New
repository secret**. Add these four:

| Secret name | Value |
|---|---|
| `ADZUNA_APP_ID` | from step 1 |
| `ADZUNA_APP_KEY` | from step 1 |
| `GMAIL_ADDRESS` | viratdharla04@gmail.com |
| `GMAIL_APP_PASSWORD` | the 16-character code from step 2 |
| `TO_ADDRESS` (optional) | only add this if you want the digest sent somewhere other than GMAIL_ADDRESS |

### 5. Test it
Go to the **Actions** tab in your repo → click "SAP Security/GRC Job Alert"
on the left → click **Run workflow** → **Run workflow**. Check your inbox in
a minute or two.

After that, it runs automatically every day at 12:00 UTC (8:00 AM Eastern).
To change the time, edit the `cron` line in
`.github/workflows/job-alert.yml` (uses UTC — https://crontab.guru helps).

## Tuning it later
- **Keywords:** edit the `KEYWORDS` list in `search.py` to add/remove role
  titles.
- **Experience/salary rule:** edit `MIN_YEARS` and
  `MIN_SALARY_IF_UNDER_MIN_YEARS` in `search.py`.
- **Look-back window:** `MAX_DAYS_OLD` controls how far back each run
  searches (2 days is a safe buffer for a daily cron so nothing gets missed
  if a run fails).
- **Add more sources later:** the same pattern (fetch → classify → email)
  can be extended with other job APIs, or with a parser for LinkedIn/Indeed
  job-alert emails if you want broader coverage — happy to add that next if
  this first version works well for you.

## Why not LinkedIn/Indeed directly?
Neither offers a public API for searching job postings, and scraping them
violates their Terms of Service (real risk of account/IP blocks). This bot
uses Adzuna, a legitimate aggregator with a free public API, to stay
reliable and avoid that risk. If you want LinkedIn/Indeed postings
specifically, the compliant route is setting up their native job-alert
emails and having this bot parse those — ask and I'll add that module.
