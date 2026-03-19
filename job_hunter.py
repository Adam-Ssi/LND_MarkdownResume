"""
job_hunter.py — Job Discovery Module for Resume Builder

Extracts query terms from a Markdown resume, scrapes live job listings from
JobStreet PH and LinkedIn (public/guest API), ranks them by cosine similarity
against the resume text, and falls back to manual search URLs when live
scraping is blocked.
"""
from __future__ import annotations

import math
from typing import Any
import random
import re
import time
from collections import Counter
from urllib.parse import quote_plus, urlencode

import httpx
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Pyright ≤1.1.x has broken generic slice stubs for str/list.__getitem__.
# Use this helper everywhere we'd write `lst[:n]` to stay error-free.
# ---------------------------------------------------------------------------
def _head(seq: "Any", n: int) -> list:  # type: ignore[type-arg]
    """Return the first n items from any iterable (slice-free, pyright-safe)."""
    out = []
    for i, item in enumerate(seq):
        if i >= n:
            break
        out.append(item)
    return out

# ---------------------------------------------------------------------------
# User-Agent pool
# ---------------------------------------------------------------------------
_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.3; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0",
]


def _random_headers(referer: str = "") -> dict[str, str]:
    h = {
        "User-Agent": random.choice(_USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "DNT": "1",
    }
    if referer:
        h["Referer"] = referer
    return h


def _sleep(min_s: float = 1.0, max_s: float = 3.0) -> None:
    time.sleep(random.uniform(min_s, max_s))


# ---------------------------------------------------------------------------
# Resume parser — extract title + top-5 skills
# ---------------------------------------------------------------------------

def extract_query(markdown_text: str) -> dict[str, str | list[str]]:
    """Return {"title": str, "skills": [str, ...]} from Markdown resume text."""
    title = ""
    skills: list[str] = []

    # ── Job title: first H3 under the Experience section ──────────────────
    exp_match = re.search(
        r"##\s+Experience\b.*?\n+###\s+(.+?)(?=\n)",
        markdown_text, re.IGNORECASE | re.DOTALL,
    )
    if exp_match:
        raw = exp_match.group(1).strip()
        # Strip " — Company Name" suffix
        title = re.split(r"\s*[—–-]\s*", raw)[0].strip()

    # ── Fallback: look for an explicit Title/Role label ───────────────────
    if not title:
        label_match = re.search(
            r"\*{0,2}(?:Title|Role|Position|Current\s+Role)\*{0,2}\s*[:\|]\s*(.+)",
            markdown_text, re.IGNORECASE,
        )
        if label_match:
            title = label_match.group(1).strip(" *")

    # ── Fallback: first H2 section that looks like a job title ───────────
    if not title:
        for line in markdown_text.splitlines():
            m = re.match(r"^##\s+(.+)$", line)
            if m:
                candidate = m.group(1).strip()
                if any(kw in candidate.lower() for kw in [
                    "engineer", "developer", "analyst", "designer",
                    "manager", "scientist", "architect", "consultant",
                    "specialist", "lead", "officer", "director",
                ]):
                    title = candidate
                    break

    # ── Skills: everything in the ## Skills section ───────────────────────
    skills_match = re.search(
        r"##\s+Skills\b(.+?)(?=\n##|\Z)",
        markdown_text, re.IGNORECASE | re.DOTALL,
    )
    if skills_match:
        skills_text = skills_match.group(1)
        # Extract capitalised tokens (tech skills are usually title-case)
        raw = re.findall(
            r"\b([A-Z][a-zA-Z+#.]{1,}(?:\s+[A-Z][a-zA-Z+#.]*){0,2})\b",
            skills_text,
        )
        stop = {
            "Languages", "Frameworks", "Infrastructure", "Databases",
            "Tools", "Skills", "Libraries", "Platforms", "Other",
            "And", "Or", "The",
        }
        seen: set[str] = set()
        for s in raw:
            if s not in stop and s not in seen:
                skills.append(s)
                seen.add(s)
            if len(skills) >= 5:
                break

    return {"title": title, "skills": _head(skills, 5)}


# ---------------------------------------------------------------------------
# Cosine similarity (pure stdlib — no scikit-learn needed)
# ---------------------------------------------------------------------------

def _cosine(text_a: str, text_b: str) -> float:
    if not text_a.strip() or not text_b.strip():
        return 0.0
    tokens_a = re.findall(r"\b[a-z0-9+#.]{2,}\b", text_a.lower())
    tokens_b = re.findall(r"\b[a-z0-9+#.]{2,}\b", text_b.lower())
    va, vb = Counter(tokens_a), Counter(tokens_b)
    common = set(va) & set(vb)
    dot = sum(va[w] * vb[w] for w in common)
    mag_a = math.sqrt(sum(v * v for v in va.values()))
    mag_b = math.sqrt(sum(v * v for v in vb.values()))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


def _resume_fingerprint(resume_text: str, query: dict) -> str:
    """Build a focused comparison string from the resume.

    Instead of comparing the full resume (which dilutes scores because
    most of its text is narrative prose), we use the title + skills +
    first Experience bullet points so the cosine score reflects how
    closely the *role and tech stack* match.
    """
    parts: list[str] = []

    title = query.get("title", "")
    skills = query.get("skills", [])
    if title:
        # repeat title tokens to boost its weight
        parts.append((title + " ") * 4)
    if skills:
        parts.append((" ".join(skills) + " ") * 3)

    # Pull skills section text verbatim
    m = re.search(r"##\s+Skills\b(.+?)(?=\n##|\Z)", resume_text, re.IGNORECASE | re.DOTALL)
    if m:
        parts.append(m.group(1))

    # Pull first Experience entry (first 300 chars)
    m2 = re.search(r"##\s+Experience\b(.+?)(?=\n##|\Z)", resume_text, re.IGNORECASE | re.DOTALL)
    if m2:
        exp_text: str = m2.group(1)
        parts.append(exp_text[:300])  # type: ignore[index]

    fallback: str = resume_text
    return " ".join(parts) if parts else fallback[:800]  # type: ignore[index]


def _score_job(fingerprint: str, job: dict) -> float:
    """Score a job against the resume fingerprint.

    Falls back to title-overlap bonus when the description is sparse
    (e.g. LinkedIn cards that only carry title + company).
    """
    description = job.get("description", "").strip()
    base = _cosine(fingerprint, description) if description else 0.0

    # Title-keyword overlap bonus: if the job title shares words with the
    # resume title, bump the score so relevant roles surface higher.
    fp_words = set(re.findall(r"\b[a-z]{3,}\b", fingerprint.lower()))
    jt_words  = set(re.findall(r"\b[a-z]{3,}\b", job.get("title", "").lower()))
    overlap = len(fp_words & jt_words)
    bonus = min(overlap * 0.06, 0.35)   # cap at +35 pp

    return min(base + bonus, 1.0)


# ---------------------------------------------------------------------------
# Manual search URL generator (always works)
# ---------------------------------------------------------------------------

def build_manual_urls(title: str, skills: list[str], location: str) -> dict[str, str]:
    query = " ".join(filter(None, [title] + _head(skills, 2)))
    q_enc = quote_plus(query)
    l_enc = quote_plus(location)
    slug_q = q_enc.replace("+", "-").lower()
    slug_l = l_enc.replace("+", "-").lower()
    return {
        "jobstreet": (
            f"https://www.jobstreet.com.ph/jobs/{slug_q}-jobs"
            f"?q={q_enc}&l={l_enc}"
        ),
        "linkedin": (
            f"https://www.linkedin.com/jobs/search/"
            f"?keywords={q_enc}&location={l_enc}&f_TPR=r604800"
        ),
        "indeed": f"https://ph.indeed.com/jobs?q={q_enc}&l={l_enc}",
    }


# ---------------------------------------------------------------------------
# JobStreet PH scraper
# ---------------------------------------------------------------------------

def _scrape_jobstreet(
    title: str, skills: list[str], location: str, max_results: int
) -> list[dict]:
    # Use title only for a broad field-level search; skills narrow it too much
    query = title or " ".join(_head(skills, 2))
    q_enc = quote_plus(query)
    l_enc = quote_plus(location)

    # Try the Chalice Search API first (inspected from network traffic)
    api_url = (
        "https://www.jobstreet.com.ph/api/chalice-search/v4/search"
        f"?siteKey=PH-Main&sourcesystem=houston"
        f"&where={l_enc}&keywords={q_enc}&pageSize={max_results}"
        f"&locale=en-PH&isDesktop=true"
    )
    headers = _random_headers("https://www.jobstreet.com.ph/")
    headers["Accept"] = "application/json, text/plain, */*"

    try:
        _sleep(0.8, 2.0)
        with httpx.Client(timeout=12, follow_redirects=True) as client:
            resp = client.get(api_url, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                jobs = []
                for item in data.get("data", []):
                    jid = item.get("id", "")
                    desc = (item.get("teaser") or "") + " " + (item.get("content") or "")
                    jobs.append({
                        "title":       item.get("title", ""),
                        "company":     (item.get("advertiser") or {}).get("description", ""),
                        "location":    (item.get("jobLocation") or {}).get("label", location),
                        "description": desc.strip(),
                        "url":         f"https://www.jobstreet.com.ph/job/{jid}" if jid else "",
                        "source":      "JobStreet",
                    })
                if jobs:
                    return [j for j in jobs if j["title"]]
    except Exception:
        pass

    # HTML fallback
    html_url = (
        f"https://www.jobstreet.com.ph/jobs/{quote_plus(query).replace('%20', '-')}-jobs"
        f"?q={q_enc}&l={l_enc}"
    )
    try:
        _sleep(1.0, 2.5)
        with httpx.Client(timeout=12, follow_redirects=True) as client:
            resp = client.get(html_url, headers=_random_headers("https://www.jobstreet.com.ph/"))
            resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        jobs = []
        for card in _head(soup.select("article[data-job-id]"), max_results):
            title_el   = card.select_one("h3[class*='title'], a[class*='title']")
            company_el = card.select_one("[class*='company'], [class*='advertiser']")
            location_el = card.select_one("[class*='location']")
            link_el     = card.select_one("a[href]")
            desc_el     = card.select_one("[class*='teaser'], [class*='abstract']")
            if not title_el:
                continue
            href = link_el["href"] if link_el else ""
            if href and not href.startswith("http"):
                href = "https://www.jobstreet.com.ph" + href
            jobs.append({
                "title":       title_el.get_text(strip=True),
                "company":     company_el.get_text(strip=True) if company_el else "",
                "location":    location_el.get_text(strip=True) if location_el else location,
                "description": desc_el.get_text(strip=True) if desc_el else "",
                "url":         href,
                "source":      "JobStreet",
            })
        return jobs
    except Exception:
        return []


# ---------------------------------------------------------------------------
# LinkedIn public guest API scraper
# ---------------------------------------------------------------------------

def _scrape_linkedin(
    title: str, skills: list[str], location: str, max_results: int
) -> list[dict]:
    # Broad search by title so more relevant roles surface
    query = title or " ".join(_head(skills, 2))
    params = urlencode({
        "keywords": query,
        "location": location,
        "f_TPR":    "r604800",   # posted in the past week
        "start":    0,
    })
    url = f"https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?{params}"

    try:
        _sleep(1.5, 3.0)
        with httpx.Client(timeout=12, follow_redirects=True) as client:
            resp = client.get(url, headers=_random_headers("https://www.linkedin.com/"))
            resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        jobs = []
        for card in _head(soup.find_all("li"), max_results):
            title_el    = card.find("h3", class_=re.compile("title"))
            company_el  = card.find("h4", class_=re.compile("subtitle"))
            location_el = card.find("span", class_=re.compile("location"))
            link_el     = card.find("a", class_=re.compile("full-link|card-link"))
            if not title_el:
                continue
            href = link_el.get("href", "") if link_el else ""
            # Strip tracking params from LinkedIn URL
            href = href.split("?")[0] if href else ""
            jobs.append({
                "title":       title_el.get_text(strip=True),
                "company":     company_el.get_text(strip=True) if company_el else "",
                "location":    location_el.get_text(strip=True) if location_el else location,
                "description": (
                    f"{title_el.get_text(strip=True)} "
                    f"{company_el.get_text(strip=True) if company_el else ''}"
                ),
                "url":         href,
                "source":      "LinkedIn",
            })
        return jobs
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def find_matching_jobs(
    resume_text: str,
    location: str = "Philippines",
    max_results: int = 15,
) -> dict:
    """
    Extract query terms from resume, scrape live jobs, score by cosine
    similarity, and return ranked results + manual fallback URLs.
    """
    if not resume_text.strip():
        return {"query": {}, "jobs": [], "manual_urls": {}, "scraped": False}

    query = extract_query(resume_text)
    title  = query["title"]
    skills = query["skills"]  # type: ignore[assignment]

    manual_urls = build_manual_urls(title, skills, location)

    all_jobs: list[dict] = []

    js_jobs = _scrape_jobstreet(title, skills, location, max_results)
    all_jobs.extend(js_jobs)

    _sleep(0.5, 1.5)

    li_jobs = _scrape_linkedin(title, skills, location, max_results)
    all_jobs.extend(li_jobs)

    # Build focused fingerprint (title + skills + experience snippet) then score
    fingerprint = _resume_fingerprint(resume_text, query)  # type: ignore[arg-type]
    for job in all_jobs:
        job["match_pct"] = int(_score_job(fingerprint, job) * 1000) / 10

    all_jobs.sort(key=lambda j: j["match_pct"], reverse=True)

    return {
        "query":       query,
        "jobs":        _head(all_jobs, max_results),
        "manual_urls": manual_urls,
        "scraped":     len(all_jobs) > 0,
    }
