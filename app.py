from flask import Flask, request, render_template, jsonify, Response
import yt_dlp
import logging
import os
import json
import requests
import re

app = Flask(__name__)

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("adfree_player.log"),
        logging.StreamHandler()
    ]
)

VIDEO_LOG_FILE = "video_log.json"
SITE_LOG_FILE = "site_log.json"

# ----------------------------
# Helper: Log video play
# ----------------------------
def log_video(video_id, title, quality, size_mb, action):
    try:
        if os.path.exists(VIDEO_LOG_FILE):
            with open(VIDEO_LOG_FILE, "r") as f:
                log_data = json.load(f)
        else:
            log_data = []

        log_entry = {
            "video_id": video_id,
            "title": title,
            "quality": quality,
            "size_mb": size_mb,
            "action": action
        }
        log_data.append(log_entry)
        with open(VIDEO_LOG_FILE, "w") as f:
            json.dump(log_data, f, indent=2)
        logging.info(f"{action} -> {title} ({video_id}) [{quality}] ~{size_mb}MB")
    except Exception as e:
        logging.error(f"Video logging failed: {e}")

# ----------------------------
# Helper: Log site access
# ----------------------------
def log_site(url, action):
    try:
        if os.path.exists(SITE_LOG_FILE):
            with open(SITE_LOG_FILE, "r") as f:
                log_data = json.load(f)
        else:
            log_data = []
        log_entry = {
            "url": url,
            "action": action
        }
        log_data.append(log_entry)
        with open(SITE_LOG_FILE, "w") as f:
            json.dump(log_data, f, indent=2)
        logging.info(f"{action} -> {url}")
    except Exception as e:
        logging.error(f"Site logging failed: {e}")

# ----------------------------
# Helper: Get YouTube video info
# ----------------------------
def get_video_info(url):
    ydl_opts = {
        "quiet": True,
        "skip_download": True,
        "forcejson": True,
        "simulate": True,
        "format": "bestvideo+bestaudio/best",
        "logger": logging.getLogger()
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        # Gather formats for quality selection
        formats = []
        for f in info.get("formats", []):
            if f.get("acodec") != "none" and f.get("vcodec") != "none":
                fmt = {
                    "format_id": f.get("format_id"),
                    "ext": f.get("ext"),
                    "resolution": f.get("format_note") or f.get("resolution"),
                    "filesize": round(f.get("filesize",0)/1024/1024, 2)  # MB
                }
                formats.append(fmt)
        return {
            "id": info.get("id"),
            "title": info.get("title"),
            "formats": formats,
            "duration": info.get("duration"),
            "next_videos": info.get("entries", [])  # for playlists
        }

# ----------------------------
# Routes
# ----------------------------

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/proxy")
def proxy_page():
    return render_template("proxy.html")

@app.route("/get_video", methods=["POST"])
def get_video():
    data = request.json
    url = data.get("url")
    if not url:
        return jsonify({"error": "No URL provided"}), 400
    try:
        info = get_video_info(url)
        return jsonify(info)
    except Exception as e:
        logging.error(f"Error fetching video: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/log_play", methods=["POST"])
def log_play():
    data = request.json
    log_video(
        video_id=data.get("video_id"),
        title=data.get("title"),
        quality=data.get("quality"),
        size_mb=data.get("size_mb"),
        action=data.get("action")
    )
    return jsonify({"status":"ok"})

@app.route("/proxytool")
def proxytool():
    site = request.args.get("site")
    if not site:
        return "No site provided", 400
    try:
        r = requests.get(site)
        html = r.text
        # Remove scripts and comments to block ads
        html = re.sub(r"<script.*?>.*?</script>", "", html, flags=re.DOTALL|re.IGNORECASE)
        html = re.sub(r"<!--.*?-->", "", html, flags=re.DOTALL)
        log_site(site, "PROXY_LOAD")
        return Response(html, content_type="text/html")
    except Exception as e:
        logging.error(f"Proxy error: {e}")
        return f"Error: {e}", 500

@app.route("/health")
def health():
    return "OK", 200

# ----------------------------
# Run
# ----------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
