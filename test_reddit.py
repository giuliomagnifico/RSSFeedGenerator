"""Focused, offline tests for the Reddit HTML feed generator."""
import tempfile
import unittest
from datetime import timezone
from pathlib import Path
from unittest.mock import Mock, patch

import reddit


def sample(post_id, title, when):
    return (
        f'<shreddit-post post-id="{post_id}" post-title="{title}" '
        f'permalink="/r/italy/comments/{post_id}/example/" '
        f'author="example_user" created-timestamp="{when}">'
        '<div slot="text-body">Test description</div>'
        '</shreddit-post>'
    )


class RedditFeedTests(unittest.TestCase):
    def test_html_parsing_and_sorting(self):
        html = (
            sample("abc123", "Old post", "2026-11-18T10:00:00.000Z")
            + sample("def456", "New post", "2026-11-19T10:00:00.000Z")
            + sample("abc123", "Duplicate post", "2026-11-18T10:00:00.000Z")
        )
        posts = reddit.parse_posts(html)
        self.assertEqual([p["id"] for p in posts], ["def456", "abc123"])
        self.assertEqual(posts[0]["link"], "https://www.reddit.com/r/italy/comments/def456/example/")
        self.assertEqual(posts[0]["author"], "example_user")
        self.assertEqual(posts[0]["published"].tzinfo, timezone.utc)

    def test_guids_and_dates_round_trip(self):
        post = reddit.parse_posts(sample("abc123", "Example", "2026-11-19T10:00:00Z"))[0]
        import lxml.etree as ET
        xml = ET.fromstring(reddit.build_feed([post]))
        item = xml.find("./channel/item")
        self.assertEqual(item.findtext("guid"), "reddit:t3_abc123")
        self.assertEqual(item.find("guid").get("isPermaLink"), "false")
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp) / "feed.xml"
            file.write_bytes(reddit.build_feed([post]))
            self.assertEqual(reddit.load_existing(file)[0]["id"], "abc123")

    def test_reject_unrelated_links_and_missing_dates(self):
        html = sample("abc123", "Valid", "2026-11-19T10:00:00Z")
        html += sample("zzz999", "No time", "")
        html += '<shreddit-post post-id="foo123" post-title="Wrong" permalink="/r/other/comments/foo123/no/" created-timestamp="2026-11-19T10:00:00Z"/>'
        self.assertEqual(len(reddit.parse_posts(html)), 1)

    def test_preserve_previous_feed_on_missing_posts(self):
        post = reddit.parse_posts(sample("abc123", "Example", "2026-11-19T10:00:00Z"))[0]
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "reddit-italy.xml"
            original = reddit.build_feed([post])
            output.write_bytes(original)
            response = Mock()
            response.headers = {"Content-Type": "text/html"}
            response.text = "<html>Blocked</html>"
            response.raise_for_status.return_value = None
            with patch.object(reddit, "OUTPUT", output), patch.object(reddit.requests, "get", return_value=response):
                with self.assertRaisesRegex(ValueError, "No valid Reddit posts"):
                    reddit.generate()
            self.assertEqual(output.read_bytes(), original)

    def test_maximum_items(self):
        posts = []
        for i in range(120):
            p = reddit.parse_posts(sample(f"p{i:05d}", f"Post {i}", f"2026-11-19T10:{i % 60:02d}:00Z"))[0]
            posts.append(p)
        retained = sorted({p["id"]: p for p in posts}.values(), key=lambda p: p["published"], reverse=True)[:reddit.MAX_ITEMS]
        self.assertEqual(len(retained), 100)


if __name__ == "__main__":
    unittest.main()
