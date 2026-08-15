"""
SAP Security / GRC Consultant job alert bot.

Pulls fresh postings from the Adzuna job API (free, legit, no ToS risk),
filters them against experience/salary rules, dedupes against previously
seen postings, and emails a digest.

Rule: include a job if
  - it mentions 4+ years experience, OR
  - it mentions less than 4 years AND advertises salary >= $120,000, OR
  - years of experience can't be determined from the text (shown so
    nothing potentially relevant is silently dropped; flagged clearly).
"""

import os
import re
import json
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests

# ---- Config ----------------------------------------------------------

ADZUNA_APP_ID = os.environ["ADZUNA_APP_ID"]
ADZUNA_APP_KEY = os.environ["ADZUNA_APP_KEY"]
GMAIL_ADDRESS = os.environ["GMAIL_ADDRESS"]
GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]
TO_ADDRESS = os.environ.get("TO_ADDRESS", GMAIL_ADDRESS)

COUNTRY = "us"
MAX_DAYS_OLD = 2          # look back window each run (daily cron)
RESULTS_PER_PAGE = 50
MIN_YEARS = 4
MIN_SALARY_IF_UNDER_MIN_YEARS = 120000
SEEN_FILE = "seen_jobs.json"

KEYWORDS = [
    "SAP Security Consultant",
    "SAP GRC Consultant",
    "SAP GRC Analyst",
    "SAP Security Analyst",
    "SAP Authorization",
    "SAP Access Control",
    "SAP IAM",
    "S/4HANA Security",
    "SAP Segregation of Duties",
    "SAP Fiori Security",
]

# ---- Helpers -----------------------------------------------------------

YEARS_RE = re.compile(
    r"(\d{1,2})\s*\+?\s*(?:years?|yrs?)\b(?:\s+of)?(?:\s+experience)?",
    re.IGNORECASE,
)


def extract_min_years(text: str):
    """Return the smallest 'N years' figure mentioned, or None if none found."""
    if not text:
        return None
    matches = [int(m) for m in YEARS_RE.findall(text)]
    matches = [m for m in matches if 0 < m <= 25]  # sanity filter
    return min(matches) if matches else None


def load_seen():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r") as f:
            return set(json.load(f))
    return set()


def save_seen(seen_ids):
    with open(SEEN_FILE, "w") as f:
        json.dump(sorted(seen_ids), f)


def fetch_jobs_for_keyword(keyword, page=1):
    url = f"https://api.adzuna.com/v1/api/jobs/{COUNTRY}/search/{page}"
    params = {
        "app_id": ADZUNA_APP_ID,
        "app_key": ADZUNA_APP_KEY,
        "what": keyword,
        "results_per_page": RESULTS_PER_PAGE,
        "max_days_old": MAX_DAYS_OLD,
        "sort_by": "date",
    }
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json().get("results", [])


def classify(job):
    """Return (include: bool, reason: str) for a job dict from Adzuna."""
    text = " ".join(
        filter(None, [job.get("title", ""), job.get("description", "")])
    )
    min_years = extract_min_years(text)
    salary_min = job.get("salary_min")
    salary_max = job.get("salary_max")
    best_salary = max([v for v in (salary_min, salary_max) if v], default=None)

    if min_years is None:
        return True, "Experience level not specified in posting"
    if min_years >= MIN_YEARS:
        return True, f"{min_years}+ yrs experience listed"
    if best_salary and best_salary >= MIN_SALARY_IF_UNDER_MIN_YEARS:
        return True, f"{min_years} yrs required, but salary ~${best_salary:,.0f}"
    return False, "Under 4 yrs and salary below $120K or unlisted"


def build_email_html(matches):
    if not matches:
        return None
    rows = []
    for job, reason in matches:
        title = job.get("title", "Untitled role")
        company = (job.get("company") or {}).get("display_name", "Unknown company")
        location = (job.get("location") or {}).get("display_name", "Unspecified")
        url = job.get("redirect_url", "#")
        contract_time = job.get("contract_time", "")
        contract_type = job.get("contract_type", "")
        salary_min = job.get("salary_min")
        salary_max = job.get("salary_max")
        salary_str = ""
        if salary_min or salary_max:
            lo = f"${salary_min:,.0f}" if salary_min else "?"
            hi = f"${salary_max:,.0f}" if salary_max else "?"
            salary_str = f"{lo} - {hi}"
        rows.append(f"""
        <tr style="border-bottom:1px solid #e5e5e5;">
          <td style="padding:10px 8px;">
            <a href="{url}" style="font-weight:600;color:#0b5fff;text-decoration:none;">{title}</a><br>
            <span style="color:#555;">{company} &middot; {location}</span><br>
            <span style="color:#888;font-size:12px;">
              {contract_time} {contract_type} {'&middot; ' + salary_str if salary_str else ''}
            </span><br>
            <span style="color:#0a8a3c;font-size:12px;">Why shown: {reason}</span>
          </td>
        </tr>
        """)
    return f"""
    <html><body style="font-family:Arial,sans-serif;">
    <h2>SAP Security / GRC Job Digest — {datetime.now().strftime('%b %d, %Y')}</h2>
    <p>{len(matches)} new matching posting(s):</p>
    <table style="border-collapse:collapse;width:100%;max-width:700px;">
    {''.join(rows)}
    </table>
    </body></html>
    """


def send_email(html_body, count):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"SAP Security/GRC Job Alert — {count} new match(es)"
    msg["From"] = GMAIL_ADDRESS
    msg["To"] = TO_ADDRESS
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_ADDRESS, TO_ADDRESS, msg.as_string())


# ---- Main ---------------------------------------------------------------

def main():
    seen = load_seen()
    matches = []
    all_ids_this_run = set()

    for kw in KEYWORDS:
        try:
            jobs = fetch_jobs_for_keyword(kw)
        except requests.RequestException as e:
            print(f"[warn] fetch failed for '{kw}': {e}")
            continue

        for job in jobs:
            job_id = str(job.get("id"))
            if not job_id or job_id in seen or job_id in all_ids_this_run:
                continue
            all_ids_this_run.add(job_id)

            include, reason = classify(job)
            if include:
                matches.append((job, reason))

    if matches:
        html = build_email_html(matches)
        send_email(html, len(matches))
        print(f"Sent digest with {len(matches)} matching job(s).")
    else:
        print("No new matching jobs this run.")

    save_seen(seen | all_ids_this_run)


if __name__ == "__main__":
    main()
