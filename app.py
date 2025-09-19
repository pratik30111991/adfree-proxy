# --- add at top if not already ---
import requests
from urllib.parse import urlparse
# -------------------------------

# Replace your existing get_video_info function with this one:

INVIDIOUS_INSTANCES = [
    "https://yewtu.cafe",
    "https://yewtu.cafe",            # duplicate intentionally low - add more if you know
    "https://yewtu.eu",             # example instances — availability varies
    "https://yewtu.herokuapp.com",
    "https://yewtu.privacy.com",    # note: some of these are placeholders; add working ones you find
    "https://yewtu.snopyta.org",
    "https://yewtu.kavin.rocks",
    "https://yewtu.zcodex.org"
]

def parse_video_id(url):
    # Extract video id from common youtube URL formats
    try:
        u = url.strip()
        if "youtu.be/" in u:
            return u.split("youtu.be/")[1].split("?")[0].split("&")[0]
        if "watch" in u and "v=" in u:
            return urlparse(u).query.split("v=")[1].split("&")[0]
        # fallback naive
        return u.split("/")[-1].split("?")[0]
    except:
        return None

def formats_from_invidious_json(j):
    fmts = []
    # Invidious returns 'formats' or 'adaptiveFormats' depending on instance
    cand = j.get("formats") or j.get("adaptiveFormats") or []
    for f in cand:
        # Build minimal format fields used by frontend: format_id, ext, resolution, filesize
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
    # dedupe and sort by resolution (attempt)
    seen = set()
    out = []
    for ff in fmts:
        key = (ff["resolution"], ff["ext"], ff["format_id"])
        if key in seen:
            continue
        seen.add(key)
        out.append(ff)
    return out

def try_invidious(video_id):
    """Try multiple Invidious instances to fetch video info. Return dict similar to yt-dlp output or raise."""
    errors = []
    for inst in INVIDIOUS_INSTANCES:
        try:
            api = inst.rstrip("/") + f"/api/v1/videos/{video_id}"
            resp = requests.get(api, timeout=10, headers={"User-Agent":"Mozilla/5.0"})
            if resp.status_code != 200:
                errors.append(f"{inst} status {resp.status_code}")
                continue
            j = resp.json()
            # Some instances return 'error' field
            if isinstance(j, dict) and j.get("error"):
                errors.append(f"{inst} err {j.get('error')}")
                continue
            fmts = formats_from_invidious_json(j)
            return {
                "id": j.get("videoId") or video_id,
                "title": j.get("title") or j.get("video_title") or f"yt:{video_id}",
                "formats": fmts,
                "duration": j.get("lengthSeconds") or j.get("duration"),
                "next_videos": []  # Invidious may have related videos in 'related'
            }
        except Exception as e:
            errors.append(f"{inst} exc {e}")
            continue
    raise Exception("Invidious fallbacks failed: " + " | ".join(errors))


def get_video_info(url):
    """
    Robust video info fetcher:
    1) Try yt-dlp (best effort)
    2) If yt-dlp fails due to sign-in/bot check, try Invidious instances automatically
    Returns: { id, title, formats:[{format_id, ext, resolution, filesize}], duration, next_videos }
    """
    # 1) Try yt-dlp first
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
            # Build formats similar to previous
            formats = []
            for f in info.get("formats", []):
                # keep only playable combined or video+audio adaptive (as earlier)
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
        # Detect sign-in/bot related messages
        if "Sign in to confirm" in errstr or "not a bot" in errstr or "cookies" in errstr or "This video is unavailable" in errstr:
            # Attempt invidious fallbacks
            vid = parse_video_id(url)
            if not vid:
                raise Exception("Cannot parse video id and yt-dlp failed: " + errstr)
            logging.info(f"Attempting Invidious fallbacks for {vid}")
            try:
                return try_invidious(vid)
            except Exception as inv_err:
                logging.error(f"Invidious fallback failed: {inv_err}")
                # Raise original yt-dlp error plus fallback details
                raise Exception(f"yt-dlp error: {errstr} ; Invidious fallback error: {inv_err}")
        else:
            # for other errors, re-raise
            raise
