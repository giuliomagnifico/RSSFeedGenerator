#!/usr/bin/env python3

import os
import Config
import requests

from lxml import etree as ET
from bs4 import BeautifulSoup
from readability import Document
from time import gmtime, strftime
from urllib.parse import urljoin, urlparse, urlunparse

header_desktop = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:141.0) Gecko/20100101 Firefox/141.0",
    "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.7,en;q=0.3",
}

timeoutconnection = 120

rssfile = Config.outputpath + "fanpage.xml"

EXCLUDED_PATHS = {
    "/",
    "/attualita/",
    "/politica/",
    "/spettacolo/",
    "/sport/",
    "/innovazione/",
    "/musica-e-cultura/",
    "/stile-e-trend/",
    "/roma/",
    "/milano/",
    "/napoli/",
    "/esteri/",
    "/redazione/",
    "/privacy-policy/",
}


def normalize_article_url(url):
    parsed = urlparse(url)

    return urlunparse(
        (
            "https",
            "www.fanpage.it",
            parsed.path,
            "",
            "",
            "",
        )
    )


def is_article_url(url):
    parsed = urlparse(url)

    if parsed.netloc not in ("fanpage.it", "www.fanpage.it"):
        return False

    path = parsed.path

    if path in EXCLUDED_PATHS:
        return False

    if path.startswith((
        "/tag/",
        "/autore/",
        "/foto/",
        "/video/",
        "/direct/",
        "/studios/",
        "/redazione/",
        "/privacy-policy/",
        "/cookie-policy/",
        "/p",
    )):
        return False

    # Gli articoli di Fanpage hanno normalmente almeno
    # categoria + slug, per esempio:
    # /attualita/titolo-articolo/
    parts = [part for part in path.split("/") if part]

    if len(parts) < 2:
        return False

    return True


def make_feed():
    root = ET.Element("rss")
    root.set("version", "2.0")

    channel = ET.SubElement(root, "channel")

    title = ET.SubElement(channel, "title")
    title.text = "Fanpage.it RSS Feed"

    link = ET.SubElement(channel, "link")
    link.text = "https://www.fanpage.it/"

    description = ET.SubElement(channel, "description")
    description.text = "RSS feed degli articoli pubblicati su Fanpage.it"

    language = ET.SubElement(channel, "language")
    language.text = "it-IT"

    generator = ET.SubElement(channel, "generator")
    generator.text = "RSSFeedGenerator - Fanpage.it"

    tree = ET.ElementTree(root)

    tree.write(
        rssfile,
        pretty_print=True,
        xml_declaration=True,
        encoding="UTF-8"
    )


def add_feed(titlefeed, descriptionfeed, linkfeed):
    linkfeed = normalize_article_url(linkfeed)

    parser = ET.XMLParser(remove_blank_text=True)
    tree = ET.parse(rssfile, parser)

    root = tree.getroot()
    channel = root.find("channel")

    # Evita duplicati
    for item in channel.findall("item"):
        link = item.find("link")

        if link is not None and link.text == linkfeed:
            return

    # Mantieni massimo 20 articoli
    items = channel.findall("item")

    if len(items) >= 20:
        channel.remove(items[-1])

    item = ET.SubElement(channel, "item")

    title = ET.SubElement(item, "title")
    title.text = titlefeed

    link = ET.SubElement(item, "link")
    link.text = linkfeed

    description = ET.SubElement(item, "description")
    description.text = descriptionfeed

    pubDate = ET.SubElement(item, "pubDate")
    pubDate.text = strftime(
        "%a, %d %b %Y %H:%M:%S +0000",
        gmtime()
    )

    channel.find(".//generator").addnext(item)

    tree = ET.ElementTree(root)

    tree.write(
        rssfile,
        pretty_print=True,
        xml_declaration=True,
        encoding="UTF-8"
    )


def scrap_fanpage(url):
    response = requests.get(
        url,
        headers=header_desktop,
        timeout=timeoutconnection
    )

    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    articles = []

    for anchor in soup.find_all("a", href=True):
        absolute_url = urljoin(url, anchor["href"])
        absolute_url = normalize_article_url(absolute_url)

        if not is_article_url(absolute_url):
            continue

        if absolute_url not in articles:
            articles.append(absolute_url)

    # Prendiamo i primi 20 articoli unici trovati nella homepage
    return articles[:20]


def main():
    url = "https://www.fanpage.it/"

    list_of_articles = scrap_fanpage(url)

    print("Articoli trovati:")
    for article in list_of_articles:
        print(article)

    if not os.path.exists(rssfile):
        make_feed()

    for urlarticolo in list_of_articles:
        try:
            response = requests.get(
                urlarticolo,
                headers=header_desktop,
                timeout=timeoutconnection
            )

            response.raise_for_status()

            document = Document(response.text)

            title = document.short_title()
            description = document.summary()

            add_feed(
                title,
                description,
                urlarticolo
            )

        except Exception as error:
            print(
                "Errore durante l'elaborazione di",
                urlarticolo,
                ":",
                error
            )


if __name__ == "__main__":
    main()
