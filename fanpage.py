#!/usr/bin/env python3

import Config
import requests

SOURCE_FEED = "https://www.fanpage.it/feed/"
rssfile = Config.outputpath + "fanpage.xml"
timeoutconnection = 120

headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
    "Accept": "application/rss+xml, application/xml, text/xml;q=0.9, */*;q=0.8",
    "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
}


def main():
    response = requests.get(
        SOURCE_FEED,
        headers=headers,
        timeout=timeoutconnection,
        allow_redirects=True,
    )

    print(f"GET {SOURCE_FEED} -> {response.status_code}")
    response.raise_for_status()

    content_type = response.headers.get("Content-Type", "")
    print(f"Content-Type: {content_type}")

    content = response.content

    if b"<rss" not in content and b"<feed" not in content:
        raise RuntimeError("Fanpage response does not appear to be an RSS/Atom feed")

    with open(rssfile, "wb") as feed_file:
        feed_file.write(content)

    print(f"Saved {rssfile} ({len(content)} bytes)")


if __name__ == "__main__":
    main()
