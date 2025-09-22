from flask import Flask, render_template, request, jsonify
import requests
import re
from urllib.parse import urlencode

app = Flask(__name__)

ARCHIVE_API = "https://archive.org/advancedsearch.php"
METADATA_API = "https://archive.org/metadata/{}"

def parse_files_for_qualities(files):
    """
    Given metadata 'files' list from archive.org, build usable audio/video URLs
    and a qualities list. Returns a dict: {
      'audio_files': {'64kb': url, '128kb': url, ...},
      'video_files': {'360p': url, '480p': url, ...}
    }
    """
    audio_files = {}
    video_files = {}

    for f in files:
        name = f.get("name", "")
        fmt = f.get("format", "").lower()
        # audio bitrates (common naming: *_64kb.mp3, *_128kb.mp3)
        m = re.search(r'(\d{2,3}k)\.mp3$', name)
        if m and ("mp3" in fmt or name.endswith(".mp3")):
            label = m.group(1)  # e.g., 64k, 128k
            audio_files[label] = f"https://archive.org/download/{f.get('source') or f.get('name','')}"  # fallback
            # better construct using identifier and exact name will be set later in caller

        # direct mp3 without bitrate in name
        if name.endswith(".mp3") and "mp3" in fmt:
            # name like track.mp3
            audio_files.setdefault("mp3", None)
            audio_files["mp3"] = None

        # video resolutions often in name like 360p, 720p
        m2 = re.search(r'(\d{3,4}p)\.mp4$', name)
        if m2 and name.endswith(".mp4"):
            label = m2.group(1)
            video_files[label] = None

        # mp4 without resolution
        if name.endswith(".mp4"):
            video_files.setdefault("mp4", None)

    return {"audio": audio_files, "video": video_files}

def fetch_archive_songs(query="", rows=15, page=1):
    """
    Search archive.org for audio/video items. For each result,
    fetch the metadata to find direct file URLs and available qualities.
    """
    # build query: if user typed something, match title or creator; otherwise mediatype audio OR video
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
        # fetch metadata for files list
        try:
            meta = requests.get(METADATA_API.format(identifier), timeout=12).json()
        except Exception:
            continue

        files = meta.get("files", [])
        # find playable files and qualities
        audio_map = {}
        video_map = {}
        for f in files:
            name = f.get("name", "")
            fmt = f.get("format", "").lower()
            # full direct url:
            direct = f"https://archive.org/download/{identifier}/{name}"
            if name.endswith(".mp3") or "audio" in fmt:
                # bitrate detection
                m = re.search(r'(\d{2,3}k)\.mp3$', name)
                if m:
                    audio_map[m.group(1)] = direct
                else:
                    # fallback tag using format or simple mp3
                    key = "mp3"
                    if key not in audio_map:
                        audio_map[key] = direct
            if name.endswith(".mp4") or "video" in fmt:
                m2 = re.search(r'(\d{3,4}p)\.mp4$', name)
                if m2:
                    video_map[m2.group(1)] = direct
                else:
                    # try name contains resolution digit but not typical pattern
                    m3 = re.search(r'(\d{3,4})', name)
                    if m3 and name.endswith(".mp4"):
                        label = f"{m3.group(1)}p"
                        video_map[label] = direct
                    else:
                        video_map.setdefault("mp4", direct)

        # choose a representative audio/video url (prefer bitrate-labeled)
        audio_url = None
        video_url = None
        audio_qualities = []
        video_qualities = []
        for k, v in sorted(audio_map.items(), key=lambda x: (len(x[0]), x[0])):
            if v:
                audio_qualities.append(k)
                if not audio_url:
                    audio_url = v
        for k, v in sorted(video_map.items(), key=lambda x: (len(x[0]), x[0])):
            if v:
                video_qualities.append(k)
                if not video_url:
                    video_url = v

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
    # page param for infinite scroll
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
    app.run(host="0.0.0.0", port=int(__import__("os").environ.get("PORT", 10000)), debug=False)
