from flask import Flask, render_template, request, jsonify
import requests

app = Flask(__name__)

ARCHIVE_API = "https://archive.org/advancedsearch.php"

def fetch_archive_songs(query="", rows=15):
    query_str = f'title:("{query}")' if query else 'mediatype:(audio video)'
    params = {
        'q': query_str,
        'fl[]': ['identifier', 'title', 'creator', 'date', 'mediatype'],
        'sort[]': 'date desc',
        'rows': rows,
        'page': 1,
        'output': 'json'
    }
    r = requests.get(ARCHIVE_API, params=params)
    if r.status_code != 200:
        return []
    docs = r.json().get('response', {}).get('docs', [])
    songs = []

    for d in docs:
        identifier = d.get('identifier')
        mediatype = d.get('mediatype','audio')

        # ✅ Metadata fetch karo
        meta_url = f"https://archive.org/metadata/{identifier}"
        meta_res = requests.get(meta_url).json()
        files = meta_res.get("files", [])

        audio_url, video_url, qualities = "", "", []

        for f in files:
            name = f.get("name", "")
            if name.endswith(".mp3") and not audio_url:
                audio_url = f"https://archive.org/download/{identifier}/{name}"
                qualities.append("mp3")
            if name.endswith(".mp4") and not video_url:
                video_url = f"https://archive.org/download/{identifier}/{name}"
                qualities.append("mp4")

        if not audio_url and not video_url:
            continue  # skip if nothing playable

        thumbnail = f"https://archive.org/services/img/{identifier}"
        songs.append({
            "title": d.get('title', 'Unknown'),
            "artist": d.get('creator', 'Unknown'),
            "year": d.get('date', 'Unknown'),
            "category": mediatype,
            "audio_url": audio_url,
            "video_url": video_url,
            "thumbnail": thumbnail,
            "qualities": qualities or ["default"]
        })
    return songs

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/default_songs")
def default_songs():
    songs = fetch_archive_songs(rows=15)
    return jsonify(songs)

@app.route("/search")
def search():
    query = request.args.get("q", "")
    songs = fetch_archive_songs(query=query, rows=20)
    return jsonify(songs)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)
