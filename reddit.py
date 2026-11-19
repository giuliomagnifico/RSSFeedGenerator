#!/usr/bin/env python3
"""Generate an RSS feed from the public HTML of r/italy/new (no Reddit API)."""
import os
import re
import tempfile
from datetime import datetime, timezone
from email.utils import format_datetime, parsedate_to_datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from lxml import etree as ET

SOURCE = "https://www.reddit.com/r/italy/new/"
OUTPUT = Path(__file__).resolve().parent / "reddit-italy.xml"
MAX_ITEMS = 100
POST_ID = re.compile(r"^[a-z0-9]{5,12}$", re.I)
URL_ID = re.compile(r"/r/italy/comments/([a-z0-9]+)/", re.I)
HEADERS = {
    "User-Agent": "RSSFeedGenerator/1.0 (public RSS metadata; https://github.com/giuliomagnifico/RSSFeedGenerator)",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "it-IT,it;q=0.9,en;q=0.7",
}


def parse_date(value):
    if not value:
        return None
    try:
        result = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        try:
            result = parsedate_to_datetime(value)
        except (TypeError, ValueError, IndexError):
            return None
    if result.tzinfo is None:
        result = result.replace(tzinfo=timezone.utc)
    return result.astimezone(timezone.utc)


def canonical_url(value):
    if not value:
        return None
    parsed = urlparse(urljoin(SOURCE, value))
    if parsed.hostname not in ("reddit.com", "www.reddit.com", "old.reddit.com"):
        return None
    match = URL_ID.search(parsed.path + "/")
    if not match:
        return None
    # Keep the comment URL but discard tracking parameters/fragments.
    return "https://www.reddit.com" + parsed.path.rstrip("/") + "/"


def parse_posts(html):
    soup = BeautifulSoup(html, "html.parser")
    results = {}
    for element in soup.select("shreddit-post"):
        href = element.get("permalink") or element.get("content-href")
        if not href:
            anchor = element.select_one('a[href*="/r/italy/comments/"]')
            href = anchor.get("href") if anchor else None
        link = canonical_url(href)
        if not link:
            continue
        match = URL_ID.search(link)
        post_id = (element.get("post-id") or match.group(1)).removeprefix("t3_").lower()
        if not POST_ID.fullmatch(post_id) or post_id != match.group(1).lower():
            continue
        title = element.get("post-title")
        if not title:
            title_node = element.select_one('a[id^="post-title"], [slot="title"]')
            title = title_node.get_text(" ", strip=True) if title_node else None
        published = parse_date(element.get("created-timestamp"))
        if not title or not published:
            continue
        author = (element.get("author") or "").removeprefix("u/").strip()
        description = ""
        body = element.select_one('[slot="text-body"], [slot="post-media-container"] [slot="text-body"]')
        if body:
            description = body.get_text(" ", strip=True)[:4000]
        results[post_id] = {
            "id": post_id,
            "title": title.strip(),
            "link": link,
            "author": author,
            "published": published,
            "description": description,
        }
    return sorted(results.values(), key=lambda post: post["published"], reverse=True)


def load_existing(path):
    if not path.exists():
        return []
    tree = ET.parse(str(path))
    posts = []
    for item in tree.findall("./channel/item"):
        guid = item.findtext("guid") or ""
        post_id = guid.removeprefix("reddit:t3_")
        link = canonical_url(item.findtext("link"))
        match = URL_ID.search(link) if link else None
        published = parse_date(item.findtext("pubDate"))
        if not match or post_id != match.group(1) or not published:
            continue
        posts.append({
            "id": post_id,
            "title": item.findtext("title") or "",
            "link": link,
            "author": item.findtext("author") or "",
            "published": published,
            "description": item.findtext("description") or "",
        })
    return posts


def build_feed(posts):
    root = ET.Element("rss", version="2.0")
    channel = ET.SubElement(root, "channel")
    for name, value in (
        ("title", "r/italy — nuovi post"),
        ("link", SOURCE),
        ("description", "Nuovi post pubblici di r/italy, ordinati per data"),
        ("language", "it-IT"),
        ("generator", "RSSFeedGenerator Reddit HTML"),
    ):
        ET.SubElement(channel, name).text = value
    for post in posts:
        item = ET.SubElement(channel, "item")
        for name, value in (
            ("title", post["title"]),
            ("link", post["link"]),
            ("guid", "reddit:t3_" + post["id"]),
            ("pubDate", format_datetime(post["published"])),
            ("description", post["description"]),
            ("author", post["author"]),
        ):
            node = ET.SubElement(item, name)
            node.text = value
            if name == "guid":
                node.set("isPermaLink", "false")
    return ET.tostring(root, encoding="UTF-8", xml_declaration=True, pretty_print=True)


def generate():
    response = requests.get(SOURCE, headers=HEADERS, timeout=25)
    response.raise_for_status()
    if "text/html" not in response.headers.get("Content-Type", "").lower():
        raise ValueError("Reddit did not return HTML")
    new_posts = parse_posts(response.text)
    if not new_posts:
        raise ValueError("No valid Reddit posts found; preserving existing XML")
    previous = load_existing(OUTPUT)
    merged = {post["id"]: post for post in previous}
    merged.update({post["id"]: post for post in new_posts})
    posts = sorted(merged.values(), key=lambda post: post["published"], reverse=True)[:MAX_ITEMS]
    payload = build_feed(posts)
    # Replace only after successfully collecting and validating a nonempty feed.
    ET.fromstring(payload)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="wb", dir=OUTPUT.parent, prefix=".reddit-", suffix=".xml", delete=False) as handle:
            temporary = handle.name
            handle.write(payload)
        os.replace(temporary, OUTPUT)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)
    print(f"Updated {OUTPUT.name}: {len(posts)} posts ({len(new_posts)} found in HTML)")


if __name__ == "__main__":
    generate()
