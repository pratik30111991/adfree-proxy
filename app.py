import os
import logging
from flask import Flask, render_template, request, jsonify
import requests

logging.basicConfig(level=logging.INFO)
app = Flask(__name__)

# Use a public Piped server (Invidious alternative)
PIPED_SERVER = "https://piped.kavin.rocks"

def fetch_video_info(url):
    """Fetch video info from Piped API"""
    try:
        # extract video id from URL
        if "youtube.com/watch?v=" in url:
            vid_id = url.split("v=")[-1].split("&")[0]
        elif "youtu.be/" in url:
            vid_id = url.split("/")[-1]
        else:
            return {"error": "Invalid YouTube URL"}

        api_url = f"{PIPED_SERVER}/api/v1/videos/{vid_id}"
        resp = requests.get(api_url, timeout=10)
        data = resp.json()

        # Prepare formats
        formats = []
        for f in data.get("videoStreams", []):
            if f.get("url"):
                formats.append({
                    "format_id": f.get("qualityLabel", f.get("itag")),
                    "url": f.get("url"),
                    "resolution": f.get("qualityLabel"),
                    "ext": f.get("mimeType", "mp4").split("/")[1]
                })

        # Playlist / related videos (first 5)
        related = []
        for r in data.get("relatedVideos", [])[:5]:
            related.append({
                "id": r.get("videoId"),
                "title": r.get("title"),
                "url": f"https://www.youtube.com/watch?v={r.get('videoId')}"
            })

        current = {
            "id": vid_id,
            "title": data.get("title"),
            "formats": formats
        }

        return {"current": current, "next_videos": related}

    except Exception as e:
        logging.error(f"Error fetching video: {e}")
        return {"error": str(e)}

# Routes
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/get_video", methods=["POST"])
def get_video():
    data = request.get_json() or {}
    url = data.get("url")
    if not url:
        return jsonify({"error": "No URL provided"}), 400
    info = fetch_video_info(url)
    if "error" in info:
        return jsonify({"error": info["error"]}), 500
    # log video access
    logging.info(f"Fetched video: {info['current']['title']} ({info['current']['id']})")
    return jsonify(info)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
