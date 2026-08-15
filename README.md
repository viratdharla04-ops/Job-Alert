SAP Security / GRC Job Alert Bot
Runs daily on GitHub Actions (free) and emails you new SAP Security/GRC job
postings (full-time and contract, all companies, any location) to
viratdharla04@gmail.com.
Sources:
Adzuna — a broad job aggregator (company sites, boards, agencies).
Not LinkedIn or Indeed's own data.
LinkedIn + Indeed — via your own native job-alert emails, read out of
Gmail. Neither platform offers a public search API, so this is the
compliant way to include them without risking your account.
Filter logic: shows a job if it lists 4+ years experience, OR lists
under 4 years but pays $120K+, OR doesn't mention experience at all (shown
so nothing potentially relevant is hidden — flagged in the email so you can
tell at a glance).
One-time setup (about 15 minutes)
1. Get a free Adzuna API key
Go to https://developer.adzuna.com and register (free, no card needed).
Copy your App ID and App Key from the dashboard.
2. Create a Gmail App Password
Gmail won't accept your normal password for automated sending/reading.
Turn on 2-Step Verification: https://myaccount.google.com/security
Go to https://myaccount.google.com/apppasswords
Create an app password (name it e.g. "job-bot") and copy the 16-character
code it gives you.
3. Enable IMAP on Gmail (needed to read LinkedIn/Indeed alert emails)
Open Gmail → Settings (gear icon) → See all settings.
Go to the Forwarding and POP/IMAP tab.
Under "IMAP access," select Enable IMAP → Save changes.
(It's on by default for most accounts — just double check.)
4. Set up native job alerts on LinkedIn and Indeed
LinkedIn: Run a job search with your target keywords (e.g. "SAP
Security Consultant", "SAP GRC") and filters (location, full-time/
contract). Click the bell/alert icon on the search results page,
set frequency to daily, and make sure it's set to email you at
viratdharla04@gmail.com.
Indeed: Run the same kind of search, then click "Get new jobs for
this search by email" near the top of the results, set it to send to
viratdharla04@gmail.com.
Repeat for a few keyword variants if you like (SAP Security, SAP GRC,
SAP Authorization, etc.) — each becomes its own alert.
5. Create a GitHub repo
Go to https://github.com/new, create a new private repo.
Upload all the files from this folder into it, keeping the
`.github/workflows/` folder structure intact.
6. Add your secrets
In your repo: Settings → Secrets and variables → Actions → New
repository secret. Add these:
Secret name	Value
`ADZUNA_APP_ID`	from step 1
`ADZUNA_APP_KEY`	from step 1
`GMAIL_ADDRESS`	viratdharla04@gmail.com
`GMAIL_APP_PASSWORD`	the 16-character code from step 2 (used for both sending the digest and reading alert emails)
`TO_ADDRESS`	viratdharla04@gmail.com
7. Test it
Go to the Actions tab → "SAP Security/GRC Job Alert" → Run
workflow → Run workflow. Check your inbox in a minute or two
(and Spam/Promotions, just in case).
After that, it runs automatically every day. To change the schedule, edit
the `cron` line in `.github/workflows/job-alert.yml` (uses UTC).
Tuning it later
Keywords (Adzuna): edit `KEYWORDS` in `search.py`.
Experience/salary rule: edit `MIN_YEARS` and
`MIN_SALARY_IF_UNDER_MIN_YEARS` in `search.py`.
Look-back window: `MAX_DAYS_OLD` controls both the Adzuna search
window and how many days back the bot checks for LinkedIn/Indeed alert
emails. Currently set wide (30 days) to validate the setup — once you
confirm it's working well, dial it down to 2-3 days so the daily digest
only shows genuinely new postings instead of re-showing the backlog.
Email parsing is best-effort: LinkedIn/Indeed can change their email
templates over time, which may require small parsing tweaks in
`email_alerts.py`. If a run finds 0 email-based results but you know
alert emails exist in your inbox, that's the most likely reason — let
me know and I can help debug the specific format.
Why not scrape LinkedIn/Indeed directly?
Neither offers a public API for searching job postings, and scraping them
violates their Terms of Service (real risk of account/IP blocks). This
bot uses Adzuna's legitimate aggregator API plus your own native job-alert
emails to stay reliable and avoid that risk entirely.
