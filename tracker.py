import requests
import xml.etree.ElementTree as ET
import gzip
import json
import os
from datetime import datetime

DATA_DIR = "data"
EMAIL_TO = "your@email.com"


def fetch_xml(url):
    r = requests.get(url, timeout=(10,60))
    content = r.content

    if url.endswith(".gz"):
        content = gzip.decompress(content)

    return ET.fromstring(content)


def extract_sitemaps_from_robots(url):
    r = requests.get(url, timeout=(10,60))
    sitemaps = []

    for line in r.text.splitlines():
        if line.lower().startswith("sitemap:"):
            sitemaps.append(line.split(":", 1)[1].strip())

    return sitemaps


def process_sitemap(url, visited_sitemaps, urls):

    if url in visited_sitemaps:
        return

    visited_sitemaps.add(url)

    root = fetch_xml(url)

    namespace = {"ns": root.tag.split("}")[0].strip("{")}

    if root.tag.endswith("sitemapindex"):

        for sitemap in root.findall("ns:sitemap/ns:loc", namespace):
            process_sitemap(sitemap.text.strip(), visited_sitemaps, urls)

    elif root.tag.endswith("urlset"):

        for url_tag in root.findall("ns:url", namespace):

            loc = url_tag.find("ns:loc", namespace).text.strip()
            lastmod_tag = url_tag.find("ns:lastmod", namespace)

            lastmod = None
            if lastmod_tag is not None:
                lastmod = lastmod_tag.text.strip()

            urls[loc] = lastmod


def collect_urls(input_url):

    visited_sitemaps = set()
    urls = {}

    if input_url.endswith("robots.txt"):

        sitemaps = extract_sitemaps_from_robots(input_url)

        for sm in sitemaps:
            process_sitemap(sm, visited_sitemaps, urls)

    else:

        process_sitemap(input_url, visited_sitemaps, urls)

    return urls


def load_snapshot(path):

    if not os.path.exists(path):
        return {}

    with open(path) as f:
        return json.load(f)


def save_snapshot(path, data):

    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def compare(old, new):

    new_urls = []
    updated = []
    removed = []

    for url in new:
        if url not in old:
            new_urls.append(url)
        elif old[url] != new[url]:
            updated.append(url)

    for url in old:
        if url not in new:
            removed.append(url)

    return new_urls, updated, removed


def section_summary(urls):

    sections = {}

    for u in urls:

        parts = u.split("/")

        if len(parts) > 3:
            section = "/" + parts[3]
        else:
            section = "/"

        sections.setdefault(section, 0)
        sections[section] += 1

    return sections


def build_email(name, new_urls, updated, removed):

    lines = []

    lines.append(f"Site: {name}")
    lines.append(f"Time: {datetime.utcnow()}")
    lines.append("")
    lines.append(f"New URLs: {len(new_urls)}")
    lines.append(f"Updated URLs: {len(updated)}")
    lines.append(f"Removed URLs: {len(removed)}")
    lines.append("")

    if new_urls:
        lines.append("NEW URLS")
        lines += new_urls[:50]
        lines.append("")

    if updated:
        lines.append("UPDATED URLS")
        lines += updated[:50]
        lines.append("")

    if removed:
        lines.append("REMOVED URLS")
        lines += removed[:50]
        lines.append("")

    section_counts = section_summary(new_urls + updated)

    if section_counts:
        lines.append("SECTION CHANGES")
        for s, c in section_counts.items():
            lines.append(f"{s} -> {c}")

    return "\n".join(lines)


def send_email(text):

    print("EMAIL ALERT")
    print(text)


def run():

    with open("competitors.json") as f:
        config = json.load(f)

    os.makedirs(DATA_DIR, exist_ok=True)

    for comp in config["competitors"]:

        name = comp["name"]
        input_url = comp["input"]

        print("Processing:", name)

        try:

            new_data = collect_urls(input_url)

            path = f"{DATA_DIR}/{name}.json"

            old_data = load_snapshot(path)

            new_urls, updated, removed = compare(old_data, new_data)

            if new_urls or updated or removed:

                email = build_email(name, new_urls, updated, removed)
                send_email(email)

            save_snapshot(path, new_data)

        except Exception as e:

            print("ERROR:", name, e)


if __name__ == "__main__":
    run()
