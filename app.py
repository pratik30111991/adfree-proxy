# app.py
from flask import Flask, render_template, request, jsonify
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, unquote
import re
import time

app = Flask(__name__)

SITE = "https://wapking.sbs"  # target site (as you asked)
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"

session = requests.Session()
session.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"})

# --- Helpers ---------------------------------------------------------------

def get_soup(url, params=None, timeout=12):
    try:
        r = session.get(url, params=params, timeout=timeout)
        r.raise_for_status()
        return BeautifulSoup(r.text, "html.parser")
    except Exception as e:
        print(f"[get_soup] error fetching {url}: {e}")
        return None

def find_listing_links(soup):
    """
    From a WapKing-ish listing page (homepage / category / featured),
    extract unique download-page hrefs and thumbnails + titles.
    """
    links = []
    seen = set()

    if not soup:
        return links

    # Primary: anchors with class 'fileName' (observed in page excerpt)
    for a in soup.select("a.fileName"):
        href = a.get("href")
        if not href:
            continue
        href = urljoin(SITE, href)
        if href in seen:
            continue
        # find thumbnail inside anchor
        img = a.select_one("img")
        thumb = urljoin(SITE, img["src"]) if img and img.get("src") else ""
        title = (a.get_text(separator=" ", strip=True) or "").strip()
        links.append({"page": href, "title": title, "thumbnail": thumb})
        seen.add(href)

    # Fallback: any /download/ links in page
    for a in soup.select("a[href*='/download/']"):
        href = a.get("href")
        if not href:
            continue
        href = urljoin(SITE, href)
        if href in seen:
            continue
        img = a.select_one("img")
        thumb = urljoin(SITE, img["src"]) if img and img.get("src") else ""
        title = (a.get_text(separator=" ", strip=True) or "").strip()
        links.append({"page": href, "title": title, "thumbnail": thumb})
        seen.add(href)

    # Another fallback: anchors that contain ".mp3" directly (rare)
    for a in soup.select("a[href*='.mp3']"):
        href = a.get("href")
        href = urljoin(SITE, href)
        if href in seen:
            continue
        title = (a.get_text(strip=True) or href.split("/")[-1])
        links.append({"page": href, "title": title, "thumbnail": ""})
        seen.add(href)

    return links

def extract_media_from_download_page(download_url):
    """
    Given a download page URL (e.g. /download/43838/...), fetch and try to extract:
    - direct mp3 / mp4 / webm links
    - thumbnail
    - title
    Return dict with audio_url, video_url, thumbnail, title
    """
    soup = get_soup(download_url)
    if not soup:
        return {"audio_url": "", "video_url": "", "thumbnail": "", "title": ""}

    # Extract title (page <title> or h1 or anchor text)
    title = ""
    ttag = soup.find("title")
    if ttag and ttag.text:
        title = ttag.text.strip()
    if not title:
        h1 = soup.find(["h1", "h2"])
        if h1:
            title = h1.get_text(strip=True)

    # thumbnail: images under /siteuploads/thumb or img meta
    thumb = ""
    img = soup.select_one("img[src*='/siteuploads/'], img[src*='thumb']")
    if img and img.get("src"):
        thumb = urljoin(SITE, img["src"])
    # meta og:image
    if not thumb:
        meta_og = soup.find("meta", property="og:image")
        if meta_og and meta_og.get("content"):
            thumb = meta_og["content"]

    # Search for direct media links
    audio_url = ""
    video_url = ""

    # 1) audio/video <audio>/<video> tags & <source>
    for tag in soup.select("audio, video, source"):
        src = tag.get("src") or tag.get("data-src") or tag.get("data-video")
        if src:
            src = urljoin(download_url, src)
            if re.search(r"\.(mp3|m4a|ogg|wav)$", src, re.I):
                audio_url = src
                break
            if re.search(r"\.(mp4|webm|mkv)$", src, re.I):
                video_url = src
                break

    # 2) <a href="...mp3"> or links that point to siteuploads directory
    if not audio_url and not video_url:
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if href.startswith("javascript:"):
                continue
            full = urljoin(download_url, href)
            low = href.lower()
            if re.search(r"\.(mp3|m4a|ogg|wav)$", low):
                audio_url = full
                break
            if re.search(r"\.(mp4|webm|mkv)$", low):
                video_url = full
                break
            # common siteuploads path pattern
            if "/siteuploads/" in href and re.search(r"\.(mp3|mp4|m4a|webm|ogg|wav)$", href, re.I):
                if re.search(r"\.(mp4|webm|mkv)$", href, re.I):
                    video_url = full
                    break
                audio_url = full
                break

    # 3) Some pages include direct text with a URL -- try regex inside HTML
    if not audio_url and not video_url:
        text = soup.get_text(" ", strip=True)
        m = re.search(r"(https?://[^\s'\"<>]+?\.(mp3|m4a|mp4|webm|ogg|wav))", text, re.I)
        if m:
            link = m.group(1)
            if re.search(r"\.(mp4|webm|mkv)$", link, re.I):
                video_url = link
            else:
                audio_url = link

    # As final fallback: the download_url itself might be a direct file (if link ended in .mp3)
    if not audio_url and not video_url and re.search(r"\.(mp3|mp4|webm|m4a|ogg|wav)$", download_url, re.I):
        if re.search(r"\.(mp4|webm|mkv)$", download_url, re.I):
            video_url = download_url
        else:
            audio_url = download_url

    return {
        "audio_url": audio_url or "",
        "video_url": video_url or "",
        "thumbnail": thumb or "",
        "title": title or ""
    }

# --- Endpoints ------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/default_songs")
def default_songs():
    """
    Return latest songs from the site (page parameter supported).
    """
    page = int(request.args.get("page", "1"))
    results = []
    try:
        # First try a 'latest updates' page pattern
        if page <= 1:
            url = f"{SITE}/"
        else:
            # try /latest_updates/<page> (observed in sample)
            url = f"{SITE}/latest_updates/{page}"
        print(f"[default_songs] fetching listing page: {url}")
        soup = get_soup(url)
        items = find_listing_links(soup)
        # For each found listing (download page), extract media links (but limit to first N to keep response small)
        max_items = 20
        count = 0
        for it in items:
            if count >= max_items:
                break
            page_url = it["page"]
            print(f"[default_songs] extracting from: {page_url}")
            media = extract_media_from_download_page(page_url)
            if not media["audio_url"] and not media["video_url"]:
                # skip items with no media found (likely ringtones or listings)
                continue
            results.append({
                "id": page_url,
                "title": media["title"] or it.get("title") or page_url.split("/")[-1],
                "artist": "", 
                "year": "",
                "description": "",
                "category": "video" if media["video_url"] else "audio",
                "audio_url": media["audio_url"],
                "video_url": media["video_url"],
                "thumbnail": media["thumbnail"] or it.get("thumbnail", ""),
                "sources": {"default": media["audio_url"] or media["video_url"]}
            })
            count += 1
            # small sleep to be a bit polite to remote site
            time.sleep(0.2)
    except Exception as e:
        print("[default_songs] error:", e)

    return jsonify(results)

@app.route("/search")
def search():
    """
    Search: we'll use DuckDuckGo html search as a fallback to find wapking download pages.
    Returns media entries similar to default_songs.
    """
    q = request.args.get("q", "").strip()
    page = int(request.args.get("page", "1"))
    results = []
    if not q:
        return jsonify([])

    try:
        # Use DuckDuckGo HTML interface to search site:wapking.sbs <query>
        ddg_url = "https://html.duckduckgo.com/html/"
        params = {"q": f"site:wapking.sbs {q}"}
        print(f"[search] querying duckduckgo for: {params['q']}")
        r = session.post(ddg_url, data=params, timeout=10)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        # collect result links that point to wapking download pages
        found_pages = []
        for a in soup.select("a"):
            href = a.get("href", "")
            if not href:
                continue
            # Some ddg links are direct; others redirect - extract direct wapking links
            if "wapking.sbs/download" in href or "/download/" in href and "wapking" in href:
                full = href if href.startswith("http") else urljoin("https://wapking.sbs", href)
                if full not in found_pages:
                    found_pages.append(full)
            # sometimes ddg returns /l/?kh=...&uddg=<encodedURL>
            # try to decode uddg param
            m = re.search(r"uddg=(https?%3A%2F%2F[^&]+)", href)
            if m:
                decoded = unquote(m.group(1))
                if "wapking.sbs" in decoded and decoded not in found_pages:
                    found_pages.append(decoded)

        # If none found via DDG, fallback to scanning site's homepage for text matches
        if not found_pages:
            print("[search] ddg returned nothing; falling back to site homepage scan")
            homepage = get_soup(SITE + "/")
            if homepage:
                for it in find_listing_links(homepage):
                    if q.lower() in (it.get("title") or "").lower():
                        found_pages.append(it["page"])

        # Pagination of found_pages
        per_page = 20
        start = (page - 1) * per_page
        slice_pages = found_pages[start:start+per_page]

        for page_url in slice_pages:
            media = extract_media_from_download_page(page_url)
            if not media["audio_url"] and not media["video_url"]:
                continue
            results.append({
                "id": page_url,
                "title": media["title"] or page_url.split("/")[-1],
                "artist": "",
                "year": "",
                "description": "",
                "category": "video" if media["video_url"] else "audio",
                "audio_url": media["audio_url"],
                "video_url": media["video_url"],
                "thumbnail": media["thumbnail"],
                "sources": {"default": media["audio_url"] or media["video_url"]}
            })
            time.sleep(0.15)
    except Exception as e:
        print("[search] error:", e)

    return jsonify(results)

if __name__ == "__main__":
    # for Render use PORT env normally; for local dev default 10000
    import os
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=True)
