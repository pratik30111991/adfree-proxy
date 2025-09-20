from flask import Flask, render_template, request, jsonify
import requests

app = Flask(__name__)

ARCHIVE_API = "https://archive.org/advancedsearch.php"

def fetch_archive_songs(query="", rows=10):
    query_str = f'title:("{query}")' if query else 'mediatype:(audio video)'
    params = {
        'q': query_str,
        'fl[]': ['identifier', 'title', 'creator', 'date', 'mediatype', 'description', 'image'],
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
        audio_url = f"https://archive.org/download/{d.get('identifier')}/{d.get('identifier')}_64kb.mp3"
        image = d.get('image', [""])[0] if "image" in d else ""
        songs.append({
            "title": d.get('title', 'Unknown'),
            "artist": d.get('creator', 'Unknown'),
            "year": d.get('date', 'Unknown'),
            "category": d.get('mediatype', 'audio'),
            "audio_url": audio_url,
            "video_url": "",  # optional: can fetch mp4 if exists
            "thumbnail": f"https://archive.org/services/img/{d.get('identifier')}" if image else "",
            "qualities": ["64kb"]
        })
    return songs

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/default_songs")
def default_songs():
    songs = fetch_archive_songs(rows=10)
    return jsonify(songs)

@app.route("/search")
def search():
    query = request.args.get("q", "")
    songs = fetch_archive_songs(query=query, rows=15)
    return jsonify(songs)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)
