# app.py
from flask import Flask, request, render_template_string, Response
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote, unquote
import logging
import os

app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

BLOCK_HOST_FRAGMENTS = [
    "doubleclick.net", "googlesyndication", "googleadservices", "pagead2.googlesyndication",
    "google-analytics.com", "adservice.google.com", "adroll.com", "adcdn", "adsystem",
    "taboola", "outbrain", "pubmatic", "revcontent", "bnc.lt", "quantserve", "adsrvr.org",
    "serving-sys", "openx.net", "adform.net", "yahoo.com/ads", "adcolony", "unityads",
    "moatads", "adnxs.com", "adsafeprotected.com", "scorecardresearch", "zedo.com",
    "adition", "media.net", "sponsored", "advert"
]

FORM_HTML = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Ad-Free Proxy</title>
  <style>
    body{font-family:Arial,Helvetica,sans-serif;margin:28px}
    input[type=text]{width:70%;padding:8px}
    button{padding:8px 12px;margin-left:6px}
    .note{color:#444;margin-top:12px;font-size:13px}
    .frame{margin-top:18px;border:1px solid #ccc;padding:8px}
  </style>
</head>
<body>
  <h2>Ad-Free Proxy</h2>
  <form method="GET" action="/">
    <label>Enter Site URL:</label><br>
    <input type="text" name="site" placeholder="https://example.com" value="{{ site|default('') }}" required>
    <button type="submit">Load</button>
    <button type="button" onclick="document.querySelector('input[name=site]').value=''">Clear</button>
  </form>

  <div class="note">
    Tip: include full URL (https://...). This proxy rewrites links/resources to keep browsing inside the proxy.
    Heavy sites or video streaming (YouTube) may not work perfectly due to remote fetch/timeouts.
  </div>

  {% if cleaned_html %}
    <h3>Ad-free view (proxied):</h3>
    <div class="frame">{{ cleaned_html|safe }}</div>
  {% endif %}
</body>
</html>
"""

@app.route("/", methods=["GET"])
def index():
    site = request.args.get("site", "").strip()
    if not site:
        return render_template_string(FORM_HTML, site=site)

    if not site.startswith("http://") and not site.startswith("https://"):
        site = "https://" + site

    logging.info(f"User requested site: {site}")

    try:
        cleaned = fetch_and_clean(site)
        logging.info(f"Successfully cleaned site: {site}")
        return render_template_string(FORM_HTML, site=site, cleaned_html=cleaned)
    except Exception as e:
        logging.exception(f"Failed to fetch site: {site}")
        return render_template_string(FORM_HTML, site=site, cleaned_html=f"<pre>Error: {e}</pre>")

@app.route("/proxy")
def proxy_resource():
    raw_url = request.args.get("url", "")
    if not raw_url:
        return Response("Missing url", status=400)

    url = unquote(raw_url)
    if is_blocked_host(url):
        logging.info(f"BLOCKED resource: {url}")
        return Response("", status=204)

    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=15, stream=True)
        content_type = r.headers.get("Content-Type", "application/octet-stream")
        logging.info(f"Proxied resource OK: {url} ({content_type})")
        return Response(r.content, content_type=content_type)
    except Exception as ex:
        logging.exception(f"Proxy fetch failed: {url}")
        return Response("", status=502)

@app.route("/health")
def health():
    return "OK", 200

def is_blocked_host(url):
    u = url.lower()
    for frag in BLOCK_HOST_FRAGMENTS:
        if frag in u:
            return True
    return False

def absolute_url(base, link):
    try:
        return urljoin(base, link)
    except:
        return link

def rewrite_attr(base, attr_value):
    if not attr_value:
        return attr_value
    a = attr_value.strip()
    if a.startswith("javascript:") or a.startswith("data:") or a.startswith("#"):
        return a
    full = absolute_url(base, a)
    if is_blocked_host(full):
        logging.info(f"Blocked resource (rewrite stage): {full}")
        return ""
    return "/proxy?url=" + quote(full, safe='')

def fetch_and_clean(url):
    headers = {"User-Agent": "Mozilla/5.0"}
    r = requests.get(url, headers=headers, timeout=20)
    r.raise_for_status()
    content_type = r.headers.get("Content-Type","").lower()
    if "text/html" not in content_type:
        logging.info(f"Non-HTML resource requested: {url}")
        return f'<a href="{url}">Open resource (non-HTML)</a>'

    soup = BeautifulSoup(r.text, "html.parser")

    # Remove ad elements
    for tag in soup.find_all(["script", "iframe", "ins", "noscript", "object", "embed"]):
        tag.decompose()

    ad_keywords = ["ad-", "ads-", "advert", "sponsor", "banner", "cookie-consent", "consent"]
    removed = 0
    for el in soup.find_all(True):
        idv = (el.get("id") or "").lower()
        clsv = " ".join(el.get("class") or []).lower()
        if any(k in idv for k in ad_keywords) or any(k in clsv for k in ad_keywords):
            el.decompose()
            removed += 1
    logging.info(f"Removed {removed} ad-tagged elements from {url}")

    # Rewrite URLs
    for tag in soup.find_all(True):
        if tag.name == "a" and tag.has_attr("href"):
            href = tag["href"]
            if href.startswith("mailto:") or href.startswith("tel:"):
                continue
            tag["href"] = "/?site=" + quote(absolute_url(url, href), safe='')
        if tag.has_attr("src"):
            tag["src"] = rewrite_attr(url, tag["src"])
        if tag.has_attr("data-src"):
            tag["data-src"] = rewrite_attr(url, tag["data-src"])
        if tag.has_attr("srcset"):
            try:
                srcset = tag["srcset"].split(",")[0].split(" ")[0]
                tag["srcset"] = rewrite_attr(url, srcset)
            except:
                tag["srcset"] = ""

    for el in soup.find_all(True):
        for attr in list(el.attrs):
            if attr.startswith("on"):
                del el.attrs[attr]

    return str(soup)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
