from flask import Flask, render_template, request, jsonify
import requests
import re

app = Flask(__name__)

ARCHIVE_API = "https://archive.org/advancedsearch.php"
METADATA_API = "https://archive.org/metadata/{}"

def fetch_archive_songs(query="", rows=15, page=1):
    if query:
        q = f'(title:("{query}") OR creator:("{query}") OR subject:("{query}"))'
    else:
        q = 'mediatype:(audio OR video)'

    params = {
        "q": q,
        "fl[]": ["identifier", "title", "creator", "date", "mediatype", "description"],
        "sort[]": "date desc",
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
        audio_map = {}
        video_map = {}

        for f in files:
            name = f.get("name", "")
            fmt = f.get("format", "").lower()
            direct = f"https://archive.org/download/{identifier}/{name}"

            if name.endswith(".mp3") or "audio" in fmt:
                m = re.search(r'(\d{2,3}k)\.mp3$', name)
                if m:
                    audio_map[m.group(1)] = direct
                else:
                    audio_map.setdefault("mp3", direct)

            if name.endswith(".mp4") or "video" in fmt:
                m2 = re.search(r'(\d{3,4}p)\.mp4$', name)
                if m2:
                    video_map[m2.group(1)] = direct
                else:
                    video_map.setdefault("mp4", direct)

        audio_url = next(iter(audio_map.values()), "")
        video_url = next(iter(video_map.values()), "")
        audio_qualities = list(audio_map.keys())
        video_qualities = list(video_map.keys())
        if not audio_url and not video_url:
            continue

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
            "qualities": audio_qualities if audio_qualities else video_qualities
        })

    return results

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/default_songs")
def default_songs():
    page = int(request.args.get("page", 1))
    songs = fetch_archive_songs(query="", rows=15, page=page)
    return jsonify(songs)

@app.route("/search")
def search():
    q = request.args.get("q", "")
    page = int(request.args.get("page", 1))
    songs = fetch_archive_songs(query=q, rows=20, page=page)
    return jsonify(songs)

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False)
