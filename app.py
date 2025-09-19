import logging
import requests
from urllib.parse import urlparse
from flask import Flask, render_template, request, jsonify, Response
import yt_dlp
import os

logging.basicConfig(level=logging.INFO)

app = Flask(__name__)

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

def build_formats_from_info(info):
    fmts = []
    for f in info.get("formats", []):
        # keep only playable streams (video+audio combined preferred)
        # We'll present a minimal set for frontend
        try:
            filesize = 0
            if f.get("filesize"):
                filesize = round(f.get("filesize")/1024/1024, 2)
        except:
            filesize = 0
        fmt = {
            "format_id": f.get("format_id") or f.get("format"),
            "ext": f.get("ext"),
            "resolution": f.get("format_note") or f.get("resolution") or f.get("height") or "unknown",
            "filesize": filesize
        }
        fmts.append(fmt)
    # dedupe simple
    out = []
    seen = set()
    for f in fmts:
        key = (f["format_id"], f["resolution"], f["ext"])
        if key in seen: continue
        seen.add(key)
        out.append(f)
    return out

def try_yt_dlp_with_opts(url, ydl_opts):
    """Try single yt-dlp invocation and return parsed info or raise."""
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        return info

def get_video_info(url):
    """
    Try several yt-dlp strategies (no cookies) to avoid sign-in when possible.
    If all fail and cookies.txt exists, try with cookies as a last resort.
    """
    # Base options (no download)
    base_opts = {
        "quiet": True,
        "skip_download": True,
        "forcejson": True,
        "simulate": True,
        # prefer combined formats when possible
        "format": "bestvideo+bestaudio/best",
        # avoid verbose console output - we use logging
    }

    # Variants to try (ordered)
    variants = []

    # 1) Default
    variants.append(dict(base_opts))

    # 2) Try with mobile-like user agent (sometimes bypasses bot checks)
    v2 = dict(base_opts)
    v2["http_headers"] = {"User-Agent": "Mozilla/5.0 (Linux; Android 10; Mobile) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0 Mobile Safari/537.36"}
    variants.append(v2)

    # 3) Try extractor args to request android player_client (helps some videos)
    v3 = dict(base_opts)
    v3["http_headers"] = {"User-Agent": "Mozilla/5.0 (Linux; Android 10; Mobile) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0 Mobile Safari/537.36"}
    v3["extractor_args"] = {"youtube": {"player_client": "android"}}
    variants.append(v3)

    # 4) Try with slightly relaxed retries/timeouts
    v4 = dict(base_opts)
    v4["retries"] = 1
    v4["socket_timeout"] = 15
    v4["http_headers"] = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0 Safari/537.36"}
    variants.append(v4)

    # Attempt variants
    last_error = None
    for idx, opts in enumerate(variants, start=1):
        try:
            logging.info(f"yt-dlp attempt #{idx} with opts keys: {list(opts.keys())}")
            info = try_yt_dlp_with_opts(url, opts)
            # Build normalized response
            return {
                "id": info.get("id"),
                "title": info.get("title"),
                "formats": build_formats_from_info(info),
                "duration": info.get("duration"),
                "next_videos": info.get("entries", []) or []
            }
        except Exception as e:
            last_error = str(e)
            logging.warning(f"yt-dlp attempt #{idx} failed: {e}")
            # If error clearly asks for sign-in, keep trying other strategies
            continue

    # If we reach here, no variant worked. As last-resort, if cookies.txt present, try once with it.
    cookies_path = os.path.join(os.getcwd(), "cookies.txt")
    if os.path.exists(cookies_path):
        try:
            logging.info("Trying yt-dlp with cookies.txt as last resort.")
            opts = dict(base_opts)
            opts["cookiefile"] = cookies_path
            info = try_yt_dlp_with_opts(url, opts)
            return {
                "id": info.get("id"),
                "title": info.get("title"),
                "formats": build_formats_from_info(info),
                "duration": info.get("duration"),
                "next_videos": info.get("entries", []) or []
            }
        except Exception as e:
            last_error = str(e)
            logging.warning(f"yt-dlp with cookies failed: {e}")

    # Nothing worked — return clear error that includes last yt-dlp message and guidance
    friendly = (
        "Unable to fetch video info without authentication. "
        "Some YouTube videos trigger a 'Sign in to confirm you’re not a bot' or are age/region restricted. "
        "This server tries multiple non-auth strategies (mobile UA, android player_client). "
        "If you do NOT want to provide cookies, that is OK — but those specific videos cannot be fetched server-side. "
        "To allow fetching such videos, place a browser-exported cookies.txt in the project root (optional). "
        f"Last error: {last_error}"
    )
    raise Exception(friendly)

# Routes
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/proxy")
def proxy_page():
    return render_template("proxy.html")

@app.route("/get_video", methods=["POST"])
def get_video():
    data = request.get_json() or {}
    url = data.get("url")
    if not url:
        return jsonify({"error": "No URL provided"}), 400
    try:
        info = get_video_info(url)
        return jsonify(info)
    except Exception as e:
        logging.error(f"get_video error: {e}")
        return jsonify({"error": str(e)}), 200

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
        content_type = resp.headers.get("content-type", "text/html")
        return Response(resp.content, content_type=content_type)
    except Exception as e:
        return f"Proxy error: {e}", 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
