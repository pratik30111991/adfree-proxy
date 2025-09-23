# app.py
from flask import Flask, request, jsonify
import requests
import json
from urllib.parse import quote_plus
import logging

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36"
}
YOUTUBE_SEARCH_URL = "https://www.youtube.com/results"


def extract_ytinitialdata(text):
    """
    Find ytInitialData = { ... }; in the response and return the JSON string.
    Uses brace matching to extract the full object reliably.
    """
    marker = "ytInitialData"
    idx = text.find(marker)
    if idx == -1:
        return None
    # find the '=' after marker
    eq = text.find("=", idx)
    if eq == -1:
        return None
    # find first '{' after '='
    start = text.find("{", eq)
    if start == -1:
        return None
    # brace matching
    depth = 0
    end = None
    for i in range(start, len(text)):
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if end is None:
        return None
    json_text = text[start:end]
    return json_text


def find_video_renderers(obj, out):
    """
    Recursively search parsed JSON for objects that contain 'videoRenderer'.
    Append found videoRenderer dicts to out list.
    """
    if isinstance(obj, dict):
        if "videoRenderer" in obj:
            out.append(obj["videoRenderer"])
        for v in obj.values():
            find_video_renderers(v, out)
    elif isinstance(obj, list):
        for item in obj:
            find_video_renderers(item, out)


def parse_video_renderer(vr):
    """
    Extract title, videoId, thumbnail url from a videoRenderer dict (if present).
    """
    video_id = vr.get("videoId")
    # title can be nested in runs or simpleText
    title = None
    title_obj = vr.get("title")
    if isinstance(title_obj, dict):
        # sometimes title runs exist
        runs = title_obj.get("runs")
        if runs and isinstance(runs, list) and len(runs) > 0:
            title = runs[0].get("text")
        else:
            title = title_obj.get("simpleText")
    elif isinstance(title_obj, str):
        title = title_obj

    # thumbnails
    thumbnail = None
    thumb_obj = vr.get("thumbnail")
    if isinstance(thumb_obj, dict):
        thumbs = thumb_obj.get("thumbnails")
        if thumbs and isinstance(thumbs, list):
            thumbnail = thumbs[-1].get("url")

    # fallback: try shortViewCount or descriptionSnippet for something, but we'll keep minimal
    if video_id and title:
        return {"title": title, "videoId": video_id, "thumbnail": thumbnail}
    return None


@app.route("/")
def home():
    return "YouTube Search Proxy is running!\nUse endpoint: /search?q=YOUR_QUERY\n"


@app.route("/search")
def search():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"error": "Missing query parameter 'q'"}), 400

    params = {"search_query": q}
    try:
        r = requests.get(YOUTUBE_SEARCH_URL, params=params, headers=HEADERS, timeout=10)
    except Exception as e:
        app.logger.error("Requests error: %s", e)
        return jsonify({"query": q, "results": [], "error": "fetch_failed"}), 500

    if r.status_code != 200:
        app.logger.error("YouTube returned status %s", r.status_code)
        return jsonify({"query": q, "results": [], "error": "youtube_status_%s" % r.status_code}), 500

    text = r.text

    # Try extracting ytInitialData JSON
    json_text = extract_ytinitialdata(text)
    results = []

    if json_text:
        try:
            data = json.loads(json_text)
            renderers = []
            find_video_renderers(data, renderers)
            for vr in renderers:
                parsed = parse_video_renderer(vr)
                if parsed:
                    results.append(parsed)
        except Exception as e:
            app.logger.exception("Failed to parse ytInitialData JSON: %s", e)
            results = []
    else:
        app.logger.info("ytInitialData not found; falling back to <a> tag scanning")
        # fallback: simple <a> scan for /watch?v= links with title attribute
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(text, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.startswith("/watch") and a.get("title"):
                vid = None
                # extract video id
                if "v=" in href:
                    vid = href.split("v=")[1].split("&")[0]
                else:
                    parts = href.split("/")
                    if parts:
                        vid = parts[-1]
                if vid:
                    results.append({"title": a.get("title"), "videoId": vid, "thumbnail": f"https://img.youtube.com/vi/{vid}/hqdefault.jpg"})
            if len(results) >= 15:
                break

    # dedupe by videoId and limit
    seen = set()
    unique = []
    for ritem in results:
        vid = ritem.get("videoId")
        if not vid or vid in seen:
            continue
        seen.add(vid)
        unique.append(ritem)
        if len(unique) >= 10:
            break

    return jsonify({"query": q, "results": unique})
