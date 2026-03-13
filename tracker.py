import requests
import xml.etree.ElementTree as ET
import gzip
import json
import os
from datetime import datetime

DATA_DIR = "data"


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
        line = line.strip()
        if line.lower().startswith("sitemap:"):
            sitemap = line.split(":",1)[1].strip()
            sitemaps.append(sitemap)

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

            urls[loc] = True


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
    removed_urls = []

    for url in new:
        if url not in old:
            new_urls.append(url)

    for url in old:
        if url not in new:
            removed_urls.append(url)

    return new_urls, removed_urls


def send_email(report_text):

    api_key = os.environ.get("RESEND_API_KEY")

    url = "https://api.resend.com/emails"

    payload = {
        "from": "onboarding@resend.dev",
        "to": ["sankardigitalguruL@gmail.com"],
        "subject": "SEO Competitor Sitemap Report",
        "text": report_text
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    requests.post(url, json=payload, headers=headers)


def run():

    with open("competitors.json") as f:
        config = json.load(f)

    os.makedirs(DATA_DIR, exist_ok=True)

    report = []
    report.append("SEO COMPETITOR SITEMAP REPORT")
    report.append("Run time: " + str(datetime.utcnow()))
    report.append("")

    failures = []

    for comp in config["competitors"]:

        name = comp["name"]
        input_url = comp["input"]

        report.append("================================")
        report.append(name.upper())
        report.append("================================")

        try:

            new_data = collect_urls(input_url)

            path = f"{DATA_DIR}/{name}.json"

            old_data = load_snapshot(path)

            new_urls, removed = compare(old_data, new_data)

            report.append(f"New URLs: {len(new_urls)}")
            report.append(f"Removed URLs: {len(removed)}")
            report.append("")

            if new_urls:
                report.append("NEW URLS")
                for u in new_urls:
                    report.append(u)
                report.append("")

            if removed:
                report.append("REMOVED URLS")
                for u in removed:
                    report.append(u)
                report.append("")

            if not new_urls and not removed:
                report.append("No changes")
                report.append("")

            save_snapshot(path, new_data)

        except Exception as e:

            failures.append(f"{name} -> {str(e)}")

            report.append("ERROR")
            report.append(str(e))
            report.append("")

    if failures:
        report.append("")
        report.append("FAILED SITES")
        for f in failures:
            report.append(f)

    send_email("\n".join(report))


if __name__ == "__main__":
    run()
