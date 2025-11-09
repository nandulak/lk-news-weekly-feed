#!/usr/bin/env python3
"""
Builds RSS and JSON feeds for "Sri Lanka This Week" from nuuuwan/lk_news_digest.

Key behaviours:
- Uses latest README.md plus historical editions from data/history.
- Extracts edition date and source count from markdown.
- Treats each edition as a weekly item keyed by its edition_date.
- Keeps only the latest version per edition_date.
- Includes only editions from CUTOFF_DATE onwards.
- Outputs:
    - feed.xml  (RSS 2.0 + content:encoded + atom:link rel="self")
    - feed.json (JSON Feed 1.1)
"""

import datetime as dt
import json
import re
from html import escape
from pathlib import Path
from typing import Any, Dict, List

import markdown
import requests

# Upstream source repo
SOURCE_REPO = "nuuuwan/lk_news_digest"
RAW_BASE = f"https://raw.githubusercontent.com/{SOURCE_REPO}/main"
LATEST_README_URL = f"{RAW_BASE}/README.md"
HISTORY_API_URL = (
    f"https://api.github.com/repos/{SOURCE_REPO}/contents/data/history"
)

# Public feed base (GitHub Pages)
FEED_BASE = "https://nandulak.github.io/lk-news-weekly-feed"

# Only include editions with edition_date >= this (inclusive)
CUTOFF_DATE = "2025-10-17"

# How many editions (weeks) to expose in the rolling feeds
MAX_ITEMS = 12

# HTTP session configuration
SESSION = requests.Session()
SESSION.headers.update(
    {
        "User-Agent": (
            "lk-news-digest-feed-builder/1.0 "
            "(+https://github.com/nandulak/lk-news-weekly-feed)"
        ),
        "Accept": "application/vnd.github.v3+json",
    }
)


def fetch_text(url: str) -> str:
    """Fetch plain text content from URL or raise."""
    resp = SESSION.get(url, timeout=30)
    resp.raise_for_status()
    return resp.text


def fetch_json(url: str) -> Any:
    """Fetch JSON content from URL or raise."""
    resp = SESSION.get(url, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _clean_markdown_for_feed(md_text: str) -> str:
    """
    Normalise and trim markdown so the feed focuses on the editorial digest:
    - normalise newlines
    - drop 'LastUpdated' shields/badges
    - drop trailing 'Model Prompt' section and badges (feed consumers don't need it)
    """
    md = md_text.replace("\r\n", "\n").replace("\r", "\n")

    # Drop LastUpdated badge line(s)
    md = re.sub(
        r'^\s*!\[LastUpdated\]\([^)]+\)\s*$',
        "",
        md,
        flags=re.IGNORECASE | re.MULTILINE,
    )

    # Drop "Model Prompt" section and everything that follows (if present),
    # since it's repo-facing meta rather than part of the digest.
    md = re.sub(
        r"(?ms)^##\s*Model Prompt.*$",
        "",
        md,
    )

    # Trim leading/trailing whitespace
    return md.strip()


def parse_edition(md_text: str, page_url: str) -> Dict[str, Any]:
    """
    Parse a weekly edition markdown into a structured record.

    Extract:
    - edition_date (from date range or explicit heading)
    - source_count (from '**N** English News Articles')
    - human-friendly title
    - stable id (GUID)
    - publication timestamps in RSS and ISO-8601 formats (UTC)
    - rendered HTML content
    - short plain-text summary
    """
    md = _clean_markdown_for_feed(md_text)

    # Source count: e.g. "from **175** English News Articles"
    m_count = re.search(
        r"from\s+\*\*(\d+)\*\*\s+English News Articles",
        md,
        flags=re.IGNORECASE,
    )
    source_count = int(m_count.group(1)) if m_count else None

    # Date range: between **YYYY-MM-DD** & **YYYY-MM-DD**
    m_range = re.search(
        r"between\s+\*\*(\d{4}-\d{2}-\d{2})\*\*\s*&?\s*\*\*(\d{4}-\d{2}-\d{2})\*\*",
        md,
        flags=re.IGNORECASE,
    )
    if m_range:
        start_date, end_date = m_range.group(1), m_range.group(2)
    else:
        start_date = end_date = None

    # Prefer end_date as edition_date; fallback to start_date; then explicit heading.
    edition_date = end_date or start_date
    if not edition_date:
        m_date = re.search(
            r"Sri Lanka This Week\s+[—-]\s+(\d{4}-\d{2}-\d{2})",
            md,
        )
        if m_date:
            edition_date = m_date.group(1)

    # Normalised, human-readable title
    if edition_date and source_count:
        title = f"Sri Lanka This Week — {edition_date} ({source_count} sources)"
    elif edition_date:
        title = f"Sri Lanka This Week — {edition_date}"
    else:
        title = "Sri Lanka This Week"

    # Render markdown to HTML for full content
    html = markdown.markdown(
        md,
        extensions=["extra", "sane_lists", "smarty"],
        output_format="xhtml",
    ).strip()

    # Publication datetime:
    # - If edition_date known: treat as 06:00 SLST (UTC+5:30) that day.
    # - Convert to UTC for feeds.
    if edition_date:
        naive = dt.datetime.strptime(edition_date, "%Y-%m-%d")
        lkt = naive.replace(hour=6, minute=0, second=0, microsecond=0)
        pub_dt = lkt - dt.timedelta(hours=5, minutes=30)
    else:
        # Fallback: build-time in UTC
        pub_dt = dt.datetime.utcnow().replace(microsecond=0)

    pub_dt_utc = pub_dt.replace(tzinfo=dt.timezone.utc)
    pub_rss = pub_dt_utc.strftime("%a, %d %b %Y %H:%M:%S +0000")
    pub_iso = pub_dt_utc.isoformat().replace("+00:00", "Z")

    # Stable GUID based on edition_date when available
    if edition_date:
        guid = f"lk-news-weekly-{edition_date}"
    else:
        guid = f"lk-news-weekly-{pub_dt_utc:%Y-%m-%d}"

    # Short summary: first substantial paragraph of text-only content
    text_only = re.sub(r"<[^>]+>", "", html)
    # Split into paragraphs on blank lines and normalise
    paragraphs = [
        p.strip()
        for p in re.split(r"\n\s*\n", text_only)
        if p.strip()
    ]

    cleaned_paragraphs: List[str] = []
    for p in paragraphs:
        lower = p.lower()
        # Filter out structural / meta paragraphs
        if lower.startswith("🇱🇰 sri lanka this week"):
            continue
        if "generated by" in lower and "english news articles" in lower:
            continue
        if lower.startswith("previous editions"):
            continue
        if lower.startswith("references"):
            continue
        if lower.startswith("model prompt"):
            continue
        cleaned_paragraphs.append(p)

    if cleaned_paragraphs:
        first_para = cleaned_paragraphs[0]
    elif paragraphs:
        first_para = paragraphs[0]
    else:
        first_para = ""

    first_para = first_para.replace("\n", " ").strip()
    if len(first_para) > 400:
        first_para = first_para[:400].rsplit(" ", 1)[0] + "…"

    return {
        "id": guid,
        "edition_date": edition_date,  # used for dedupe & ordering
        "title": title,
        "url": page_url,
        "content_html": html,
        "summary": first_para,
        "pub_date_rss": pub_rss,
        "pub_date_iso": pub_iso,
    }


def load_editions(max_items: int = MAX_ITEMS) -> List[Dict[str, Any]]:
    """
    Load weekly editions:

    - Latest from README.md
    - Historical from data/history via GitHub API
    - Only editions with edition_date >= CUTOFF_DATE
    - Only the latest version per edition_date (based on filename order & content)
    - Sorted newest-first by edition_date, capped at max_items
    """

    cutoff = CUTOFF_DATE
    editions_by_date: Dict[str, Dict[str, Any]] = {}

    # 1. Latest from README (current week)
    latest_md = fetch_text(LATEST_README_URL)
    latest = parse_edition(
        latest_md,
        "https://github.com/nuuuwan/lk_news_digest/blob/main/README.md",
    )
    latest_date = latest.get("edition_date")
    if latest_date and latest_date >= cutoff:
        editions_by_date[latest_date] = latest

    # 2. Historical editions from /data/history
    try:
        history_entries = fetch_json(HISTORY_API_URL)
    except Exception:
        history_entries = []

    md_files = [
        e
        for e in history_entries
        if isinstance(e, dict)
        and e.get("type") == "file"
        and e.get("name", "").lower().endswith(".md")
        and e.get("download_url")
    ]

    # Sort by filename ascending so that later (typically timestamped) names
    # appear later; we will let later entries override earlier ones. This
    # remains robust even if the exact timestamp format changes, as long as
    # filenames for the same date sort lexicographically by version.
    md_files.sort(key=lambda e: e["name"])

    for entry in md_files:
        md = fetch_text(entry["download_url"])
        ed = parse_edition(md, entry.get("html_url", entry["download_url"]))

        ed_date = ed.get("edition_date")
        if not ed_date:
            continue

        # Only editions from cutoff onwards
        if ed_date < cutoff:
            continue

        existing = editions_by_date.get(ed_date)
        if existing is None:
            editions_by_date[ed_date] = ed
        else:
            # Heuristic: treat later/longer content as the latest/best version
            if len(ed["content_html"]) >= len(existing["content_html"]):
                editions_by_date[ed_date] = ed

    # 3. Build final list: newest first
    editions = list(editions_by_date.values())
    editions.sort(
        key=lambda e: (
            e.get("edition_date") or "",
            e["pub_date_iso"],
        ),
        reverse=True,
    )

    # 4. Cap to max_items
    return editions[:max_items]


def build_rss(editions: List[Dict[str, Any]]) -> str:
    """
    Build RSS 2.0 feed with:
    - content:encoded for full HTML
    - atom:link rel="self" per RSS Best Practices Profile
    """

    last_build = dt.datetime.utcnow().replace(tzinfo=dt.timezone.utc)
    last_build_rss = last_build.strftime("%a, %d %b %Y %H:%M:%S +0000")

    lines: List[str] = []
    lines.append('<?xml version="1.0" encoding="UTF-8"?>')
    lines.append(
        '<rss version="2.0" '
        'xmlns:content="http://purl.org/rss/1.0/modules/content/" '
        'xmlns:atom="http://www.w3.org/2005/Atom">'
    )
    lines.append("  <channel>")
    lines.append("    <title>Sri Lanka This Week</title>")
    lines.append("    <link>https://github.com/nuuuwan/lk_news_digest</link>")
    lines.append(
        "    <description>"
        "Curated weekly digest of Sri Lanka news, generated from vetted "
        "English-language sources."
        "</description>"
    )
    lines.append("    <language>en-LK</language>")
    lines.append(f"    <lastBuildDate>{last_build_rss}</lastBuildDate>")
    lines.append("    <generator>lk-news-digest-feed-builder</generator>")
    # Short TTL: weekly content, but allows prompt refresh by readers
    lines.append("    <ttl>60</ttl>")
    lines.append(
        f'    <atom:link rel="self" type="application/rss+xml" '
        f'href="{FEED_BASE}/feed.xml" />'
    )

    for ed in editions:
        lines.append("    <item>")
        lines.append(f"      <title>{escape(ed['title'])}</title>")
        lines.append(f"      <link>{ed['url']}</link>")
        lines.append(
            f'      <guid isPermaLink="false">{escape(ed["id"])}</guid>'
        )
        lines.append(f"      <pubDate>{ed['pub_date_rss']}</pubDate>")
        lines.append(
            f"      <description>{escape(ed['summary'])}</description>"
        )
        lines.append("      <content:encoded><![CDATA[")
        lines.append(ed["content_html"])
        lines.append("      ]]></content:encoded>")
        lines.append("    </item>")
        lines.append("")  # visual separation between items

    lines.append("  </channel>")
    lines.append("</rss>")

    return "\n".join(lines)


def build_json_feed(editions: List[Dict[str, Any]]) -> str:
    """
    Build JSON Feed 1.1 representation.

    See: https://jsonfeed.org/version/1.1
    """

    feed: Dict[str, Any] = {
        "version": "https://jsonfeed.org/version/1.1",
        "title": "Sri Lanka This Week",
        "home_page_url": "https://github.com/nuuuwan/lk_news_digest",
        "feed_url": f"{FEED_BASE}/feed.json",
        "description": (
            "Curated weekly digest of Sri Lanka news, generated from "
            "vetted English-language sources."
        ),
        "language": "en-LK",
        "items": [],
    }

    for ed in editions:
        item: Dict[str, Any] = {
            "id": ed["id"],
            "title": ed["title"],
            "url": ed["url"],
            "date_published": ed["pub_date_iso"],
            "content_html": ed["content_html"],
        }
        # Optional but useful: short summary for feed UIs
        if ed.get("summary"):
            item["summary"] = ed["summary"]
        feed["items"].append(item)

    return json.dumps(feed, indent=2, ensure_ascii=False)


def main() -> None:
    editions = load_editions()
    out_dir = Path(".")

    rss = build_rss(editions)
    json_feed = build_json_feed(editions)

    (out_dir / "feed.xml").write_text(rss, encoding="utf-8")
    (out_dir / "feed.json").write_text(json_feed, encoding="utf-8")


if __name__ == "__main__":
    main()
