from flask import Flask, request, jsonify, render_template, send_from_directory
import requests
from bs4 import BeautifulSoup
import re
import os
from urllib.parse import urljoin, quote_plus

app = Flask(__name__, static_folder="static", template_folder="templates")

# Sites we will try to probe for results. You said you'll not restrict sources,
# but we avoid archive.org etc. Add/remove sites here if you want.
CANDIDATE_HOSTS = [
    "https://wapking.asia",
    "https://wapking.sbs",
    "https://wapking.co",
    "https://wapking.me"
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

def try_search_urls(host, q):
    """
    Try a few common search URL patterns on the host.
    Returns response text if any returns 200.
    """
    patterns = [
        f"{host}/search.php?q={quote_plus(q)}",
        f"{host}/?s={quote_plus(q)}",
        f"{host}/search?q={quote_plus(q)}",
        f"{host}/?search={quote_plus(q)}",
        f"{host}/search/{quote_plus(q)}",
    ]
    for url in patterns:
        try:
            r = requests.get(url, headers=HEADERS, timeout=10)
            if r.status_code == 200 and r.text and len(r.text) > 200:
                return r.text, url
        except Exception:
            continue
    return None, None

def extract_links_from_html(html, base):
    """Return list of (title, href) from common result containers"""
    soup = BeautifulSoup(html, "html.parser")
    results = []

    # 1) Try Google CSE-like results
    for a in soup.select("a.gs-title, a.gsc-thumbnail-inside a, div.gs-title a, .gsc-webResult a"):
        href = a.get("href")
        title = a.get_text(strip=True)
        if href and title:
            results.append((title, urljoin(base, href)))

    # 2) Generic anchors inside list items / result blocks
    if not results:
        for a in soup.select("div.list a, .list a, .file a, .item a, ul li a"):
            href = a.get("href")
            title = a.get_text(strip=True)
            if href and title:
                results.append((title, urljoin(base, href)))

    # 3) fallback: any link containing query words or '/download' or '/file'
    if not results:
        query_words = re.split(r"\s+", base)
        for a in soup.find_all("a", href=True):
            href = a["href"]
            title = a.get_text(strip=True) or href
            if any(part.lower() in href.lower() for part in ["download", "file", "song", "mp3", "singer"]) or any(w.lower() in title.lower() for w in []):
                results.append((title, urljoin(base, href)))

    # Deduplicate while preserving order
    seen = set()
    final = []
    for t, h in results:
        if h not in seen:
            seen.add(h)
            final.append((t, h))
    return final

def find_audio_on_page(url):
    """
    Follow the page and try to find direct audio urls (.mp3) or <audio> sources or links that clearly point to an mp3.
    Returns a list of audio urls (can be empty).
    """
    audios = []
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code != 200:
            return audios
        html = r.text
        soup = BeautifulSoup(html, "html.parser")

        # <audio> tags
        for audio in soup.find_all("audio"):
            src = audio.get("src")
            if src:
                audios.append(urljoin(url, src))
            # check <source> inside audio
            for source in audio.find_all("source"):
                s = source.get("src")
                if s:
                    audios.append(urljoin(url, s))

        # direct links to .mp3
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if re.search(r"\.mp3(\?.*)?$", href, re.I):
                audios.append(urljoin(url, href))

        # Any JS embedded mp3 url (simple regex)
        for m in re.findall(r"https?://[^\s'\"<>]+\.mp3[^\s'\"<>]*", html, flags=re.I):
            audios.append(m)

        # look for data attributes common on some sites
        for tag in soup.select("[data-mp3], [data-src]"):
            val = tag.get("data-mp3") or tag.get("data-src")
            if val and ".mp3" in val:
                audios.append(urljoin(url, val))
    except Exception:
        pass

    # normalize/dedupe
    seen = set()
    out = []
    for a in audios:
        if a not in seen:
            seen.add(a)
            out.append(a)
    return out

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/search")
def search():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify([])

    results = []
    # Try each candidate host until we get something
    for host in CANDIDATE_HOSTS:
        html, used_url = try_search_urls(host, q)
        if not html:
            continue
        # parse
        links = extract_links_from_html(html, host)
        # If we found links, traverse a few to find direct audio links
        for title, link in links[:20]:  # limit to first 20 to save time
            entry = {"title": title, "page_url": link, "audio": []}
            audio_urls = find_audio_on_page(link)
            if audio_urls:
                entry["audio"] = audio_urls
                # Prefer first audio as primary_url
                entry["primary_url"] = audio_urls[0]
            else:
                entry["primary_url"] = link  # fallback to page link
            results.append(entry)

        if results:
            break  # stop after first host that gave results

    # As a last resort, try fetching host homepage and scanning for likely pages
    if not results:
        for host in CANDIDATE_HOSTS:
            try:
                r = requests.get(host, headers=HEADERS, timeout=8)
                if r.status_code == 200:
                    links = extract_links_from_html(r.text, host)
                    for title, link in links[:20]:
                        if q.lower().split()[0] in title.lower() or q.lower().split()[0] in link.lower():
                            entry = {"title": title, "page_url": link, "audio": []}
                            audio_urls = find_audio_on_page(link)
                            if audio_urls:
                                entry["audio"] = audio_urls
                                entry["primary_url"] = audio_urls[0]
                            else:
                                entry["primary_url"] = link
                            results.append(entry)
                    if results:
                        break
            except Exception:
                continue

    # Final formatting cleanup: keep minimal fields for client
    cleaned = []
    for r in results:
        cleaned.append({
            "title": r.get("title")[:200],
            "url": r.get("primary_url"),
            "page_url": r.get("page_url"),
            "audio_links": r.get("audio", [])
        })

    return jsonify(cleaned)

# static files (if any)
@app.route('/static/<path:p>')
def static_files(p):
    return send_from_directory('static', p)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    # Use threaded so concurrent requests (search + UI) behave better on small render instance
    app.run(host="0.0.0.0", port=port, threaded=True)
