#!/usr/bin/env python3
import datetime as dt
import json
import re
from html import escape
from pathlib import Path

import requests
import markdown

SOURCE_REPO = "nuuuwan/lk_news_digest"
RAW_BASE = f"https://raw.githubusercontent.com/{SOURCE_REPO}/main"
LATEST_README_URL = f"{RAW_BASE}/README.md"
HISTORY_API_URL = f"https://api.github.com/repos/{SOURCE_REPO}/contents/data/history"

# How many weeks to expose in the rolling feed
MAX_ITEMS = 12

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "lk-news-digest-feed-builder/1.0 (+https://github.com/nandulak)",
    "Accept": "application/vnd.github.v3+json",
})


def fetch_text(url: str) -> str:
    resp = SESSION.get(url, timeout=30)
    resp.raise_for_status()
    return resp.text


def fetch_json(url: str):
    resp = SESSION.get(url, timeout=30)
    resp.raise_for_status()
    return resp.json()


def parse_edition(md_text: str, page_url: str) -> dict:
    """
    Parse a weekly edition markdown into a structured item:
    - title (with date & source count when available)
    - stable id
    - publication dates in RSS + ISO formats
    - full HTML content
    """

    # Source count: from "**175** English News Articles"
    m_count = re.search(
        r"from\s+\*\*(\d+)\*\*\s+English News Articles",
        md_text,
        flags=re.IGNORECASE,
    )
    source_count = int(m_count.group(1)) if m_count else None

    # Date range: between **YYYY-MM-DD** & **YYYY-MM-DD**
    m_range = re.search(
        r"between\s+\*\*(\d{4}-\d{2}-\d{2})\*\*\s*&?\s*\*\*(\d{4}-\d{2}-\d{2})\*\*",
        md_text,
        flags=re.IGNORECASE,
    )
    if m_range:
        start_date, end_date = m_range.group(1), m_range.group(2)
    else:
        start_date = end_date = None

    # Prefer end-date as edition date; fall back to explicit "Sri Lanka This Week — YYYY-MM-DD"
    edition_date = end_date or start_date
    if not edition_date:
        m_date = re.search(
            r"Sri Lanka This Week\s+[—-]\s+(\d{4}-\d{2}-\d{2})",
            md_text,
        )
        if m_date:
            edition_date = m_date.group(1)

    # Build human-friendly title
    if edition_date and source_count:
        title = f"Sri Lanka This Week — {edition_date} ({source_count} sources)"
    elif edition_date:
        title = f"Sri Lanka This Week — {edition_date}"
    else:
        title = "Sri Lanka This Week"

    # Render markdown to HTML, preserving headings + spacing
    html = markdown.markdown(
        md_text,
        extensions=["extra", "sane_lists", "smarty"],
        output_format="xhtml",
    ).strip()

    # Derive publication datetime:
    # Treat edition_date as 06:00 LKT (UTC+5:30), convert to UTC for feeds.
    if edition_date:
        naive = dt.datetime.strptime(edition_date, "%Y-%m-%d")
        lkt = naive.replace(hour=6, minute=0, second=0, microsecond=0)
        pub_dt = lkt - dt.timedelta(hours=5, minutes=30)
    else:
        pub_dt = dt.datetime.utcnow().replace(microsecond=0)

    pub_dt_utc = pub_dt.replace(tzinfo=dt.timezone.utc)
    pub_rss = pub_dt_utc.strftime("%a, %d %b %Y %H:%M:%S +0000")
    pub_iso = pub_dt_utc.isoformat().replace("+00:00", "Z")

    # Stable GUID
    guid = (
        f"lk-news-weekly-{edition_date}"
        if edition_date
        else f"lk-news-weekly-{pub_dt_utc:%Y-%m-%d}"
    )

    # Short summary = first paragraph of HTML-stripped content
    text_only = re.sub(r"<[^>]+>", "", html).strip()
    first_para = text_only.split("\n\n")[0].replace("\n", " ")
    if len(first_para) > 400:
        first_para = first_para[:400].rsplit(" ", 1)[0] + "…"

    return {
        "id": guid,
        "title": title,
        "url": page_url,
        "content_html": html,
        "summary": first_para,
        "pub_date_rss": pub_rss,
        "pub_date_iso": pub_iso,
    }


def load_editions(max_items: int = MAX_ITEMS):
    editions = []

    # Latest from README
    latest_md = fetch_text(LATEST_README_URL)
    latest = parse_edition(
        latest_md,
        "https://github.com/nuuuwan/lk_news_digest/blob/main/README.md",
    )
    editions.append(latest)

    # Historical editions from /data/history (GitHub API)
    try:
        history_entries = fetch_json(HISTORY_API_URL)
    except Exception:
        history_entries = []

    md_files = [
        e for e in history_entries
        if isinstance(e, dict)
        and e.get("type") == "file"
        and e.get("name", "").lower().endswith(".md")
        and e.get("download_url")
    ]

    # Sort by filename descending; assumes filenames include the date (which they do)
    md_files.sort(key=lambda e: e["name"], reverse=True)

    for entry in md_files:
        if len(editions) >= max_items:
            break
        md = fetch_text(entry["download_url"])
        ed = parse_edition(md, entry.get("html_url", entry["download_url"]))
        editions.append(ed)

    # Sort final list by pub_date desc (newest first)
    editions.sort(key=lambda e: e["pub_date_iso"], reverse=True)
    return editions


def build_rss(editions):
    last_build = dt.datetime.utcnow().replace(tzinfo=dt.timezone.utc)
    last_build_rss = last_build.strftime("%a, %d %b %Y %H:%M:%S +0000")

    lines = []
    lines.append('<?xml version="1.0" encoding="UTF-8"?>')
    lines.append(
        '<rss version="2.0" '
        'xmlns:content="http://purl.org/rss/1.0/modules/content/">'
    )
    lines.append("  <channel>")
    lines.append("    <title>Sri Lanka This Week</title>")
    lines.append("    <link>https://github.com/nuuuwan/lk_news_digest</link>")
    lines.append(
        "    <description>"
        "Curated weekly digest of Sri Lanka news, generated from vetted English-language sources."
        "</description>"
    )
    lines.append("    <language>en-LK</language>")
    lines.append(f"    <lastBuildDate>{last_build_rss}</lastBuildDate>")
    lines.append("    <generator>lk-news-digest-feed-builder</generator>")
    lines.append("    <ttl>60</ttl>")

    for ed in editions:
        lines.append("    <item>")
        lines.append(f"      <title>{escape(ed['title'])}</title>")
        lines.append(f"      <link>{ed['url']}</link>")
        lines.append(
            f'      <guid isPermaLink="false">{escape(ed["id"])}</guid>'
        )
        lines.append(f"      <pubDate>{ed['pub_date_rss']}</pubDate>")
        lines.append(f"      <description>{escape(ed['summary'])}</description>")
        lines.append("      <content:encoded><![CDATA[")
        lines.append(ed["content_html"])
        lines.append("      ]]></content:encoded>")
        lines.append("    </item>")
        lines.append("")  # visual separation between items

    lines.append("  </channel>")
    lines.append("</rss>")

    return "\n".join(lines)


def build_json_feed(editions):
    feed = {
        "version": "https://jsonfeed.org/version/1.1",
        "title": "Sri Lanka This Week",
        "home_page_url": "https://github.com/nuuuwan/lk_news_digest",
        # Update this once you know your actual published URL:
        "feed_url": "https://nandulak.github.io/lk-news-digest-feed/feed.json",
        "description": (
            "Curated weekly digest of Sri Lanka news, generated from "
            "vetted English-language sources."
        ),
        "language": "en-LK",
        "items": [],
    }

    for ed in editions:
        feed["items"].append(
            {
                "id": ed["id"],
                "title": ed["title"],
                "url": ed["url"],
                "date_published": ed["pub_date_iso"],
                "content_html": ed["content_html"],
            }
        )

    return json.dumps(feed, indent=2, ensure_ascii=False)


def main():
    editions = load_editions()
    out_dir = Path(".")

    rss = build_rss(editions)
    json_feed = build_json_feed(editions)

    (out_dir / "feed.xml").write_text(rss, encoding="utf-8")
    (out_dir / "feed.json").write_text(json_feed, encoding="utf-8")


if __name__ == "__main__":
    main()
