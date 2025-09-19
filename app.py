import logging
import requests
from urllib.parse import urlparse
from flask import Flask, render_template, request, jsonify, Response
import yt_dlp

# Flask app
app = Flask(__name__)

# ------------------------
# Invidious Instances
# ------------------------
INVIDIOUS_INSTANCES = [
    "https://yewtu.cafe",
    "https://yewtu.eu",
    "https://yewtu.kavin.rocks",
    "https://yewtu.zcodex.org"
]

def parse_video_id(url):
    try:
        u = url.strip()
        if "youtu.be/" in u:
            return u.split("youtu.be/")[1].split("?")[0].split("&")[0]
        if "watch" in u and "v=" in u:
            return urlparse(u).query.split("v=")[1].split("&")[0]
        return u.split("/")[-1].split("?")[0]
    except:
        return None

def formats_from_invidious_json(j):
    fmts = []
    cand = j.get("formats") or j.get("adaptiveFormats") or []
    for f in cand:
        fid = f.get("itag") or f.get("format_id") or str(f.get("contentLength", ""))[:6]
        ext = f.get("mimeType", "").split("/")[1].split(";")[0] if f.get("mimeType") else f.get("ext", "mp4")
        res = f.get("qualityLabel") or f.get("resolution") or f.get("quality")
        filesz = None
        if f.get("contentLength"):
            try:
                filesz = round(int(f.get("contentLength")) / 1024 / 1024, 2)
            except:
                filesz = None
        fmts.append({
            "format_id": fid,
            "ext": ext,
            "resolution": res or "unknown",
            "filesize": filesz or 0
        })
    # dedupe
    seen, out = set(), []
    for ff in fmts:
        key = (ff["resolution"], ff["ext"], ff["format_id"])
        if key in seen:
            continue
        seen.add(key)
        out.append(ff)
    return out

def try_invidious(video_id):
    errors = []
    for inst in INVIDIOUS_INSTANCES:
        try:
            api = inst.rstrip("/") + f"/api/v1/videos/{video_id}"
            resp = requests.get(api, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
            if resp.status_code != 200:
                errors.append(f"{inst} status {resp.status_code}")
                continue
            j = resp.json()
            if isinstance(j, dict) and j.get("error"):
                errors.append(f"{inst} err {j.get('error')}")
                continue
            fmts = formats_from_invidious_json(j)
            return {
                "id": j.get("videoId") or video_id,
                "title": j.get("title") or f"yt:{video_id}",
                "formats": fmts,
                "duration": j.get("lengthSeconds"),
                "next_videos": []
            }
        except Exception as e:
            errors.append(f"{inst} exc {e}")
            continue
    raise Exception("Invidious fallbacks failed: " + " | ".join(errors))

def get_video_info(url):
    ydl_opts = {
        "quiet": True,
        "skip_download": True,
        "forcejson": True,
        "simulate": True,
        "format": "bestvideo+bestaudio/best",
        "logger": logging.getLogger()
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            formats = []
            for f in info.get("formats", []):
                if f.get("acodec") != "none" and f.get("vcodec") != "none":
                    fmt = {
                        "format_id": f.get("format_id"),
                        "ext": f.get("ext"),
                        "resolution": f.get("format_note") or f.get("resolution"),
                        "filesize": round(f.get("filesize", 0)/1024/1024, 2) if f.get("filesize") else 0
                    }
                    formats.append(fmt)
            return {
                "id": info.get("id"),
                "title": info.get("title"),
                "formats": formats,
                "duration": info.get("duration"),
                "next_videos": info.get("entries", [])
            }
    except Exception as e:
        errstr = str(e)
        logging.warning(f"yt-dlp failed: {errstr}")
        vid = parse_video_id(url)
        if not vid:
            raise Exception("Cannot parse video id and yt-dlp failed: " + errstr)
        return try_invidious(vid)

# ------------------------
# Routes
# ------------------------

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/proxy")
def proxy_page():
    return render_template("proxy.html")

@app.route("/get_video", methods=["POST"])
def get_video():
    data = request.get_json()
    url = data.get("url")
    try:
        info = get_video_info(url)
        return jsonify(info)
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route("/log_play", methods=["POST"])
def log_play():
    data = request.get_json()
    logging.info(f"PLAY LOG: {data}")
    return jsonify({"status": "ok"})

@app.route("/proxytool")
def proxytool():
    site = request.args.get("site")
    if not site:
        return "No site given", 400
    try:
        resp = requests.get(site, timeout=10)
        return Response(resp.content, content_type=resp.headers.get("content-type", "text/html"))
    except Exception as e:
        return f"Proxy error: {e}", 500


# Entry point
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
