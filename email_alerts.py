"""
Reads LinkedIn and Indeed "Job Alert" emails out of a Gmail inbox via IMAP
and extracts individual job postings from them.

This is the compliant way to get LinkedIn/Indeed postings into the digest:
neither platform offers a public search API, and scraping either one risks
account/IP blocks (see README). Instead, YOU set up their native job-alert
emails (free, built into both platforms) for your search terms, and this
module parses those alert emails out of your inbox.

Setup required (one-time, on your end):
  1. On LinkedIn: run a job search with your target keywords/filters, then
     turn on "Job alert" for that search (bell icon on the search results
     page). Set frequency to daily.
  2. On Indeed: run a job search, click "Get new jobs for this search by
     email", set frequency to daily.
  3. Make sure both alerts deliver to the same Gmail inbox this bot reads
     (GMAIL_ADDRESS secret).
  4. Gmail IMAP must be enabled: Gmail Settings -> "Forwarding and POP/IMAP"
     -> Enable IMAP. It's on by default for most accounts.

Parsing note: this extracts job title + link via pattern matching on the
email HTML, which is best-effort (email templates can change over time).
It intentionally does not try to extract salary/years-experience from
these emails, since that data usually isn't in the alert digest itself —
those jobs are shown with "Experience level not specified", same as any
other posting where that data is missing, so the classify() rule still
applies (see search.py).
"""

import re
import html
import hashlib
import imaplib
import email as email_lib
from email.header import decode_header
from datetime import datetime, timedelta

IMAP_HOST = "imap.gmail.com"

# Sender patterns that identify each platform's alert emails.
LINKEDIN_SENDER_HINTS = ["jobalerts-noreply@linkedin.com", "@linkedin.com"]
INDEED_SENDER_HINTS = ["@indeed.com"]

# Link patterns that identify an actual job posting (vs. nav/footer links).
LINKEDIN_JOB_LINK_RE = re.compile(r"linkedin\.com/[^\"'\s]*jobs/view", re.IGNORECASE)
INDEED_JOB_LINK_RE = re.compile(
    r"indeed\.com/[^\"'\s]*(?:rc/clk|viewjob)", re.IGNORECASE
)

ANCHOR_RE = re.compile(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.IGNORECASE | re.DOTALL)
TAG_RE = re.compile(r"<[^>]+>")

# Boilerplate link text to ignore (nav links, not real job titles).
JUNK_TITLE_PATTERNS = re.compile(
    r"^(view job|apply now|see more|unsubscribe|manage alerts|view all|"
    r"see all|job alert|search again|update preferences)\b",
    re.IGNORECASE,
)


def _clean_text(raw_html_fragment: str) -> str:
    text = TAG_RE.sub("", raw_html_fragment)
    text = html.unescape(text)
    return " ".join(text.split()).strip()


def _decode_subject(raw_subject):
    if not raw_subject:
        return ""
    parts = decode_header(raw_subject)
    decoded = ""
    for part, enc in parts:
        if isinstance(part, bytes):
            decoded += part.decode(enc or "utf-8", errors="ignore")
        else:
            decoded += part
    return decoded


def _get_html_body(msg):
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    return payload.decode(charset, errors="ignore")
        return ""
    if msg.get_content_type() == "text/html":
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            return payload.decode(charset, errors="ignore")
    return ""


def _extract_jobs_from_html(body_html, job_link_re, source_label):
    jobs = []
    for href, inner_html in ANCHOR_RE.findall(body_html):
        href_unescaped = html.unescape(href)
        if not job_link_re.search(href_unescaped):
            continue
        title = _clean_text(inner_html)
        if not title or len(title) < 4 or JUNK_TITLE_PATTERNS.match(title):
            continue
        job_id = "email-" + hashlib.sha256(href_unescaped.encode()).hexdigest()[:16]
        jobs.append(
            {
                "id": job_id,
                "title": title,
                "description": "",  # not reliably available from alert emails
                "company": {"display_name": "See posting"},
                "location": {"display_name": "See posting"},
                "redirect_url": href_unescaped,
                "contract_time": "",
                "contract_type": "",
                "salary_min": None,
                "salary_max": None,
                "source": source_label,
            }
        )
    # de-dupe within this single email (same job often linked twice)
    seen_urls = set()
    unique = []
    for job in jobs:
        if job["redirect_url"] in seen_urls:
            continue
        seen_urls.add(job["redirect_url"])
        unique.append(job)
    return unique


def fetch_alert_jobs(gmail_address, gmail_app_password, since_days=2):
    """Connect to Gmail via IMAP, find recent LinkedIn/Indeed job-alert
    emails, and return a list of job dicts in the same shape used for
    Adzuna results (so they can flow through the same classify() logic)."""
    jobs = []
    try:
        imap = imaplib.IMAP4_SSL(IMAP_HOST)
        imap.login(gmail_address, gmail_app_password)
    except imaplib.IMAP4.error as e:
        print(f"[warn] IMAP login failed, skipping email alerts: {e}")
        return jobs

    try:
        imap.select("INBOX", readonly=True)
        since_date = (datetime.now() - timedelta(days=since_days)).strftime(
            "%d-%b-%Y"
        )
        status, data = imap.search(None, f'(SINCE "{since_date}")')
        if status != "OK":
            return jobs
        msg_ids = data[0].split()

        for msg_id in msg_ids:
            status, msg_data = imap.fetch(msg_id, "(RFC822)")
            if status != "OK" or not msg_data or not msg_data[0]:
                continue
            raw_email = msg_data[0][1]
            msg = email_lib.message_from_bytes(raw_email)
            from_addr = (msg.get("From") or "").lower()

            is_linkedin = any(h in from_addr for h in LINKEDIN_SENDER_HINTS)
            is_indeed = any(h in from_addr for h in INDEED_SENDER_HINTS)
            if not (is_linkedin or is_indeed):
                continue

            body_html = _get_html_body(msg)
            if not body_html:
                continue

            if is_linkedin:
                jobs.extend(
                    _extract_jobs_from_html(body_html, LINKEDIN_JOB_LINK_RE, "LinkedIn")
                )
            elif is_indeed:
                jobs.extend(
                    _extract_jobs_from_html(body_html, INDEED_JOB_LINK_RE, "Indeed")
                )
    finally:
        try:
            imap.logout()
        except Exception:
            pass

    return jobs
