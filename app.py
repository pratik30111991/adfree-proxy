from flask import Flask, request, jsonify, send_from_directory
import requests

app = Flask(__name__)

def fetch_archive_songs(q, rows=15, page=1):
    params = {
        "q": q if q else "mediatype:(audio OR video)",
        "fl[]": ["identifier","title","creator","date","mediatype","description"],
        "sort[]": "publicdate desc",
        "rows": rows,
        "page": page,
        "output": "json"
    }
    r = requests.get("https://archive.org/advancedsearch.php", params=params)
    docs = r.json().get("response", {}).get("docs", [])
    results = []
    for d in docs:
        identifier = d.get("identifier")
        files_url = f"https://archive.org/metadata/{identifier}"
        meta = requests.get(files_url).json()
        files = meta.get("files", [])
        audio_url, video_url, thumbnail = "", "", ""
        audio_qualities, video_qualities = [], []
        audio_map, video_map = {}, {}

        for f in files:
            name, fmt = f.get("name"), f.get("format","").lower()
            if not name: continue
            url = f"https://archive.org/download/{identifier}/{name}"
            if "mp3" in fmt or "ogg" in fmt:
                audio_url = url
                q = f.get("bitrate") or f.get("length") or fmt
                audio_qualities.append(q); audio_map[q] = url
            elif "mpeg4" in fmt or "h.264" in fmt or "matroska" in fmt or "webm" in fmt:
                video_url = url
                q = f.get("height") or fmt
                video_qualities.append(str(q)); video_map[str(q)] = url
            if not thumbnail and ("jpg" in fmt or "png" in fmt):
                thumbnail = url
        if not thumbnail:
            thumbnail = "https://archive.org/services/img/" + identifier

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

@app.route('/search')
def search():
    q = request.args.get("q", "")
    results = fetch_archive_songs(q)
    return jsonify({"results": results})

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

if __name__ == '__main__':
    app.run(debug=True)
