import os
import logging
from flask import Flask, render_template, request, jsonify
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
app = Flask(__name__)

DEFAULT_PIPED_INSTANCES = [
    "https://piped.video",
    "https://piped.kavin.rocks",
    "https://piped.video.kavin.rocks"
]

PIPED_SERVER = os.environ.get("PIPED_SERVER")

def get_piped_endpoints():
    if PIPED_SERVER:
        return [PIPED_SERVER.rstrip("/")]
    return [u.rstrip("/") for u in DEFAULT_PIPED_INSTANCES]

def try_fetch_from_piped(vid_id):
    last_err = None
    for base in get_piped_endpoints():
        api_url = f"{base}/api/v1/videos/{vid_id}"
        logging.info(f"Trying Piped API: {api_url}")
        try:
            resp = requests.get(api_url, timeout=10, headers={"User-Agent":"Mozilla/5.0"})
            if resp.status_code != 200:
                raise ValueError(f"HTTP {resp.status_code}")
            try:
                data = resp.json()
            except Exception as je:
                logging.error(f"JSON parse error from {base}: {je}, text={resp.text[:200]}")
                raise je
            if not isinstance(data, dict) or "title" not in data:
                raise ValueError("Unexpected JSON structure")
            logging.info(f"Piped instance succeeded: {base}")
            return data
        except Exception as e:
            last_err = e
            logging.warning(f"Piped instance {base} failed: {e}")
            continue
    raise last_err or Exception("No piped instances available")

def extract_video_id(url):
    if not url:
        return None
    u = url.strip()
    if "youtu.be/" in u:
        return u.split("youtu.be/")[-1].split("?")[0].split("&")[0]
    if "v=" in u and "youtube" in u:
        return u.split("v=")[-1].split("&")[0]
    if "/" in u:
        return u.rstrip("/").split("/")[-1]
    return u

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/get_video", methods=["POST"])
def get_video():
    data = request.get_json() or {}
    url = data.get("url")
    if not url:
        return jsonify({"error":"No URL provided"}), 400
    vid_id = extract_video_id(url)
    if not vid_id:
        return jsonify({"error":"Could not parse video id"}), 400

    try:
        piped_json = try_fetch_from_piped(vid_id)
    except Exception as e:
        logging.error(f"Error fetching from Piped: {e}")
        return jsonify({"error":f"Failed to fetch video info. Details: {str(e)}"}), 500

    formats = []
    for f in piped_json.get("videoStreams", []):
        if not f.get("url"):
            continue
        formats.append({
            "format_id": f.get("qualityLabel") or f.get("itag"),
            "url": f.get("url"),
            "resolution": f.get("qualityLabel"),
            "ext": (f.get("mimeType") or "video/mp4").split("/")[1] if f.get("mimeType") else "mp4"
        })

    related = []
    for r in piped_json.get("relatedVideos", [])[:20]:
        rid = r.get("videoId")
        if not rid:
            continue
        related.append({
            "id": rid,
            "title": r.get("title") or "",
            "url": f"https://www.youtube.com/watch?v={rid}",
            "formats": []
        })

    current = {
        "id": vid_id,
        "title": piped_json.get("title"),
        "formats": formats
    }

    logging.info(f"Fetched video: {current['title']} (id={current['id']}) formats={len(formats)} related={len(related)}")
    return jsonify({"current": current, "next_videos": related})

@app.route("/log_play", methods=["POST"])
def log_play():
    d = request.get_json() or {}
    logging.info(f"PLAY LOG: {d}")
    return jsonify({"status":"ok"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
