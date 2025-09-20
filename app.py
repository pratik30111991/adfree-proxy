import os
import logging
import threading
import time
from flask import Flask, render_template, request, jsonify
import requests

# ---------- Config ----------
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
app = Flask(__name__)

# If you have your own stable Piped/Invidious instance, set this env var:
# export PIPED_SERVER="https://your-piped.example.com"
PIPED_SERVER = os.environ.get("PIPED_SERVER")

# Long list of public Piped / Invidious-like API base URLs (may change over time).
# I included many; some may be down. The app will health-check and pick alive ones.
DEFAULT_PIPED_INSTANCES = [
    "https://piped.video",
    "https://piped.kavin.rocks",
    "https://piped.video.kavin.rocks",
    "https://piped.labstack.com",
    "https://piped.moomoo.me",
    "https://piped.pipecraft.xyz",
    "https://piped.video.iirose.dev",
    "https://piped.moomoo.me",             # duplicate tolerated
    "https://yewtu.cafe",                  # invidious-like (some endpoints differ)
    "https://yewtu.eu.org",
    "https://yewtu.cafe",                  # duplicates ok
    "https://yewtu.cafe/api/v1",           # note: some instances host on root; code handles /api/v1 prefix
    "https://yewtu.appspot.com",
    "https://yewtu.cafe", 
    "https://yewtu.privacy.com",          # placeholders; may not exist
    "https://yewtu.snopyta.org",
    "https://yewtu.org",
    "https://piped.video.kavin.rocks",     # kept as present earlier
    "https://piped.social",
    "https://piped.stoplight.io"
]

# runtime-maintained alive instances (start as empty; background thread will populate)
_alive_lock = threading.Lock()
alive_instances = []  # list of strings like "https://piped.video"

# Health check timing (seconds)
HEALTH_CHECK_INTERVAL = 60  # re-check every 60s in background


# ---------- Utilities ----------
def normalize_base(u: str) -> str:
    """Normalize base url to no trailing slash and without trailing /api/v1"""
    if not u:
        return u
    u = u.strip()
    # remove any trailing "/api/v1" or "/api/v1/"
    if u.endswith("/api/v1"):
        u = u[:-7]
    if u.endswith("/api/v1/"):
        u = u[:-8]
    return u.rstrip("/")


def get_candidate_list():
    """Return ordered list of candidates: env PIPED_SERVER first if set, else DEFAULT list."""
    if PIPED_SERVER:
        return [normalize_base(PIPED_SERVER)]
    # normalize each and unique-preserve-order
    seen = set()
    out = []
    for u in DEFAULT_PIPED_INSTANCES:
        n = normalize_base(u)
        if not n: 
            continue
        if n in seen: 
            continue
        seen.add(n)
        out.append(n)
    return out


def health_check_once(instance_base: str, timeout=6) -> bool:
    """Check whether instance_base + /api/v1/videos/test returns something (HEAD-like check).
       We will call /api/v1/videos/<invalid id> is not desirable; better to call /api/v1/health or root.
       Many Piped instances support /api/v1/health or root HTML; we'll request /api/v1/version or /api/v1/videos? (best-effort)
    """
    # Try /api/v1/version if available
    try_urls = [
        f"{instance_base}/api/v1/version",
        f"{instance_base}/api/v1/health",
        f"{instance_base}/api/v1/videos",   # may list or return HTML -> we'll just check status code 200
        f"{instance_base}/"
    ]
    headers = {"User-Agent": "Mozilla/5.0 (compatible; AdFreePlayer/1.0)"}
    for url in try_urls:
        try:
            resp = requests.get(url, timeout=timeout, headers=headers)
            if resp.status_code == 200:
                # some instances return HTML root — still OK as alive (we'll later check JSON per-video)
                return True
        except Exception:
            continue
    return False


def refresh_alive_instances():
    """Populate global alive_instances by checking candidates. Called at startup and periodically."""
    global alive_instances
    candidates = get_candidate_list()
    new_alive = []
    logging.info(f"Health-check start for {len(candidates)} candidate instances")
    for c in candidates:
        try:
            ok = health_check_once(c)
            logging.info(f"Health-check {c}: {'OK' if ok else 'FAIL'}")
            if ok:
                new_alive.append(c)
        except Exception as e:
            logging.warning(f"Health-check error for {c}: {e}")
    with _alive_lock:
        alive_instances = new_alive
    logging.info(f"Alive instances after refresh: {len(alive_instances)}")


def background_health_checker():
    """Thread target to periodically refresh alive_instances."""
    while True:
        try:
            refresh_alive_instances()
        except Exception as e:
            logging.error(f"Background health-check exception: {e}")
        time.sleep(HEALTH_CHECK_INTERVAL)


def extract_video_id(url: str) -> str | None:
    if not url:
        return None
    u = url.strip()
    if "youtu.be/" in u:
        return u.split("youtu.be/")[-1].split("?")[0].split("&")[0]
    if "v=" in u and "youtube" in u:
        return u.split("v=")[-1].split("&")[0]
    # fallback last path piece
    if "/" in u:
        return u.rstrip("/").split("/")[-1]
    return u


def try_fetch_video_json(vid_id: str):
    """Try alive instances (and fall back to candidates) to fetch video JSON.
       Returns tuple (piped_base_used, parsed_json) or raises Exception.
    """
    headers = {"User-Agent": "Mozilla/5.0 (compatible; AdFreePlayer/1.0)"}
    # snapshot alive list
    with _alive_lock:
        local_alive = list(alive_instances)

    candidates = local_alive + [c for c in get_candidate_list() if c not in local_alive]

    last_err = None
    for base in candidates:
        api_url = f"{base}/api/v1/videos/{vid_id}"
        logging.info(f"Trying instance {base} for video {vid_id}")
        try:
            resp = requests.get(api_url, timeout=12, headers=headers)
            if resp.status_code != 200:
                logging.warning(f"{base} returned HTTP {resp.status_code} for {api_url}")
                last_err = Exception(f"HTTP {resp.status_code} from {base}")
                continue
            # parse JSON
            try:
                data = resp.json()
            except Exception as je:
                logging.warning(f"JSON parse error from {base}: {je}; response starts: {resp.text[:200]!r}")
                last_err = je
                continue
            if not isinstance(data, dict) or "title" not in data:
                logging.warning(f"Unexpected JSON structure from {base}: keys={list(data.keys())}")
                last_err = Exception("Unexpected JSON structure")
                continue
            # success: mark base alive (optimistic)
            with _alive_lock:
                if base not in alive_instances:
                    alive_instances.append(base)
            logging.info(f"Success: using {base} for {vid_id}")
            return base, data
        except Exception as e:
            logging.warning(f"Instance {base} failed for video {vid_id}: {e}")
            last_err = e
            continue
    raise last_err or Exception("No available piped/invidious instances")


# ---------- Routes ----------
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/get_video", methods=["POST"])
def get_video_route():
    data = request.get_json() or {}
    url = data.get("url")
    if not url:
        return jsonify({"error": "No URL provided"}), 400
    vid_id = extract_video_id(url)
    if not vid_id:
        return jsonify({"error": "Could not parse video id"}), 400

    try:
        base_used, piped_json = try_fetch_video_json(vid_id)
    except Exception as e:
        logging.error(f"Error fetching video {vid_id}: {e}")
        return jsonify({"error": f"Failed to fetch video info. Details: {str(e)}"}), 500

    # Build formats list
    formats = []
    for f in piped_json.get("videoStreams", []) or []:
        if not f.get("url"):
            continue
        formats.append({
            "format_id": f.get("qualityLabel") or f.get("itag"),
            "url": f.get("url"),
            "resolution": f.get("qualityLabel"),
            "ext": (f.get("mimeType") or "video/mp4").split("/")[1] if f.get("mimeType") else "mp4"
        })

    # Related videos
    related = []
    for r in piped_json.get("relatedVideos", [])[:30]:
        rid = r.get("videoId")
        if not rid:
            continue
        related.append({
            "id": rid,
            "title": r.get("title") or "",
            "url": f"https://www.youtube.com/watch?v={rid}",
            "formats": []  # formats not fetched here (we will fetch when user navigates)
        })

    current = {
        "id": vid_id,
        "title": piped_json.get("title"),
        "formats": formats,
        # include which backend instance served this (helps logs)
        "served_by": base_used
    }

    logging.info(f"Returning info for {vid_id} served_by={base_used} formats={len(formats)} related={len(related)}")
    return jsonify({"current": current, "next_videos": related})


@app.route("/log_play", methods=["POST"])
def log_play():
    d = request.get_json() or {}
    logging.info(f"PLAY LOG: {d}")
    return jsonify({"status": "ok"})


# ---------- Startup ----------
def start_background_health_thread():
    t = threading.Thread(target=background_health_checker, daemon=True, name="health-checker")
    t.start()

if __name__ == "__main__":
    # Initial health check before serving
    try:
        refresh_alive_instances()
    except Exception as e:
        logging.warning(f"Initial health-check failed: {e}")
    start_background_health_thread()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
