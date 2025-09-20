from flask import Flask, render_template, request, jsonify
import requests
import yt_dlp

app = Flask(__name__)

PIPED_API = "https://piped.kavin.rocks/api/v1"

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/get_video", methods=["POST"])
def get_video():
    url = request.json.get("url")
    if not url:
        return jsonify({"error": "No URL provided"}), 400

    # Extract video ID for Piped
    video_id = url.split("watch?v=")[-1].split("&")[0] if "watch?v=" in url else url
    api_url = f"{PIPED_API}/videos/{video_id}"

    # Try fetching from Piped first
    try:
        resp = requests.get(api_url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if 'streams' in data and len(data['streams']) > 0:
                return jsonify(data)
    except Exception as e:
        print("Piped failed:", e)

    # Fallback to yt-dlp
    try:
        ydl_opts = {
            "format": "best[ext=mp4]/best",
            "quiet": True,
            "skip_download": True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            streams = []
            for f in info.get("formats", []):
                if f.get("ext") == "mp4" and f.get("url"):
                    streams.append({
                        "url": f["url"],
                        "quality": f.get("format_note"),
                        "mimeType": f.get("acodec")+"+"+f.get("vcodec")
                    })
            return jsonify({"title": info.get("title"), "streams": streams})
    except Exception as e:
        print("yt-dlp failed:", e)
        return jsonify({"error": "Failed to fetch video"}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
