from flask import Flask, render_template, request, jsonify
import requests
import re

app = Flask(__name__)

ARCHIVE_API = "https://archive.org/advancedsearch.php"
METADATA_API = "https://archive.org/metadata/{}"

def fetch_archive_songs(query="", rows=15, page=1):
    """Fetch songs from archive.org (audio/video)"""
    if query:
        q = f'(title:("{query}") OR creator:("{query}") OR subject:("{query}"))'
    else:
        q = 'mediatype:(audio OR video)'

    params = {
        "q": q,
        "fl[]": ["identifier", "title", "creator", "date", "mediatype", "description"],
        "sort[]": "publicdate desc",
        "rows": rows,
        "page": page,
        "output": "json"
    }

    try:
        resp = requests.get(ARCHIVE_API, params=params, timeout=12)
        resp.raise_for_status()
    except Exception:
        return []

    docs = resp.json().get("response", {}).get("docs", [])
    results = []

    for d in docs:
        identifier = d.get("identifier")
        if not identifier:
            continue

        try:
            meta = requests.get(METADATA_API.format(identifier), timeout=12).json()
        except Exception:
            continue

        files = meta.get("files", [])
        audio_url, video_url, thumbnail = "", "", ""
        audio_map, video_map = {}, {}
        audio_qualities, video_qualities = [], []

        for f in files:
            name = f.get("name", "")
            fmt = f.get("format", "").lower()
            if not name:
                continue
            url = f"https://archive.org/download/{identifier}/{name}"

            # Audio
            if "mp3" in fmt or "ogg" in fmt:
                audio_url = url
                q_label = f.get("bitrate") or "mp3"
                audio_qualities.append(q_label)
                audio_map[q_label] = url

            # Video
            elif "mpeg4" in fmt or "h.264" in fmt or "matroska" in fmt or "webm" in fmt:
                video_url = url
                q_label = f.get("height") or "mp4"
                video_qualities.append(str(q_label))
                video_map[str(q_label)] = url

            # Thumbnail
            if not thumbnail and ("jpg" in fmt or "png" in fmt):
                thumbnail = url

        if not thumbnail:
            thumbnail = f"https://archive.org/services/img/{identifier}"

        results.append({
            "id": identifier,
            "title": d.get("title", "Unknown"),
            "artist": d.get("creator", "Unknown"),
            "year": d.get("date", "Unknown"),
            "description": d.get("description", "") or "",
            "category": d.get("mediatype") or ("audio" if audio_url else "video"),
            "audio_url": audio_url or "",
            "video_url": video_url or "",
            "thumbnail": thumbnail,
            "qualities": audio_qualities if audio_qualities else video_qualities,
            "sources": {**audio_map, **video_map}
        })

    return results

@app.route("/default_songs")
def default_songs():
    page = int(request.args.get("page", 1))
    songs = fetch_archive_songs(query="", rows=15, page=page)
    return jsonify(songs)

@app.route("/search")
def search():
    q = request.args.get("q", "")
    page = int(request.args.get("page", 1))
    songs = fetch_archive_songs(query=q, rows=15, page=page)
    return jsonify(songs)

@app.route("/")
def index():
    return render_template("index.html")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)
