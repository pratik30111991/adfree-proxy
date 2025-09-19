import logging
import os
from flask import Flask, render_template, request, jsonify
import yt_dlp

logging.basicConfig(level=logging.INFO)
app = Flask(__name__)

def fetch_video_info(url):
    ydl_opts = {
        "quiet": True,
        "skip_download": True,
        "extract_flat": True,
        "forcejson": True,
        "format": "bestvideo+bestaudio/best"
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
    
    current = {
        "id": info.get("id"),
        "title": info.get("title"),
        "formats": [
            {
                "format_id": f.get("format_id"),
                "ext": f.get("ext"),
                "resolution": f.get("format_note") or f.get("resolution") or f.get("height") or "unknown",
                "filesize": round(f.get("filesize", 0)/1024/1024, 2)
            } for f in info.get("formats", [])
        ]
    }

    next_videos = []
    entries = info.get("entries") or []
    for e in entries[:5]:
        next_videos.append({
            "id": e.get("id"),
            "title": e.get("title")
        })

    return {"current": current, "next_videos": next_videos}

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/get_video", methods=["POST"])
def get_video():
    data = request.get_json() or {}
    url = data.get("url")
    if not url:
        return jsonify({"error": "No URL provided"}), 400
    try:
        info = fetch_video_info(url)
        return jsonify(info)
    except Exception as e:
        logging.error(f"Error fetching video: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
