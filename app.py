# app.py
# Simple proxy that fetches a target page, strips many ad elements,
# rewrites resource URLs to route through this proxy, and returns cleaned HTML.
# NOTE: This is a best-effort HTML proxy. It cannot reliably remove video-stream ads (YouTube).
from flask import Flask, request, render_template_string, Response, redirect, url_for
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote, unquote
import logging
import os

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# Simple blocklist of known ad/tracker host fragments (extend as needed)
BLOCK_HOST_FRAGMENTS = [
    "doubleclick.net", "googlesyndication", "googleadservices", "pagead2.googlesyndication",
    "google-analytics.com", "adservice.google.com", "adroll.com", "adcdn", "adsystem",
    "taboola", "outbrain", "pubmatic", "revcontent", "bnc.lt", "quantserve", "adsrvr.org",
    "serving-sys", "openx.net", "adform.net", "yahoo.com/ads", "adcolony", "unityads",
    "moatads", "adnxs.com", "adsafeprotected.com", "scorecardresearch", "zedo.com",
    "adition", "media.net", "sponsored", "advert"
]

# Minimal HTML form template
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

    # Ensure scheme
    if not site.startswith("http://") and not site.startswith("https://"):
        site = "https://" + site

    try:
        cleaned = fetch_and_clean(site)
        return render_template_string(FORM_HTML, site=site, cleaned_html=cleaned)
    except Exception as e:
        logging.exception("Failed fetch")
        return render_template_string(FORM_HTML, site=site, cleaned_html=f"<pre>Error: {e}</pre>")

@app.route("/proxy")
def proxy_resource():
    # fetch arbitrary resource via server and return it (images/css/js)
    raw_url = request.args.get("url", "")
    if not raw_url:
        return Response("Missing url", status=400)

    url = unquote(raw_url)
    # Block known ad hosts immediately
    if is_blocked_host(url):
        return Response("", status=204)

    try:
        # Stream resource - use a simple GET
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=15, stream=True)
        content_type = r.headers.get("Content-Type", "application/octet-stream")
        # Pass content-type and raw content
        return Response(r.content, content_type=content_type)
    except Exception as ex:
        logging.exception("proxy fetch failed")
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
    # ignore javascript: and data: URIs
    if a.startswith("javascript:") or a.startswith("data:") or a.startswith("#"):
        return a
    full = absolute_url(base, a)
    # if this resource is blocked, return empty
    if is_blocked_host(full):
        return ""
    # route through /proxy
    return "/proxy?url=" + quote(full, safe='')

def fetch_and_clean(url):
    headers = {"User-Agent": "Mozilla/5.0"}
    r = requests.get(url, headers=headers, timeout=20)
    r.raise_for_status()
    content_type = r.headers.get("Content-Type","").lower()
    if "text/html" not in content_type:
        # Not HTML: return a small link to resource
        return f'<a href="{url}">Open resource (non-HTML)</a>'

    soup = BeautifulSoup(r.text, "html.parser")

    # Remove script, iframe, ins, adsense, noscript, link rel=preload of ad domains
    for tag in soup.find_all(["script", "iframe", "ins", "noscript", "object", "embed"]):
        try:
            tag.decompose()
        except:
            pass

    # Remove elements with common ad-class/id keywords
    ad_keywords = ["ad-", "ads-", "advert", "sponsor", "banner", "cookie-consent", "consent"]
    for el in soup.find_all(True):
        try:
            idv = (el.get("id") or "").lower()
            clsv = " ".join(el.get("class") or []).lower()
            if any(k in idv for k in ad_keywords) or any(k in clsv for k in ad_keywords):
                el.decompose()
        except:
            pass

    # Rewrite href/src/srcset/style/background URLs to route via proxy
    for tag in soup.find_all(True):
        # href
        if tag.name == "a" and tag.has_attr("href"):
            href = tag["href"]
            if href.startswith("mailto:") or href.startswith("tel:"):
                continue
            tag["href"] = "/?site=" + quote(absolute_url(url, href), safe='')
            # open proxied links in same window (already proxied)
        # src attributes (img, script, iframe handled before)
        if tag.has_attr("src"):
            tag["src"] = rewrite_attr(url, tag["src"])
        if tag.has_attr("data-src"):
            tag["data-src"] = rewrite_attr(url, tag["data-src"])
        if tag.has_attr("srcset"):
            # simplify: convert to first src in srcset
            try:
                srcset = tag["srcset"].split(",")[0].split(" ")[0]
                tag["srcset"] = rewrite_attr(url, srcset)
            except:
                tag["srcset"] = ""
        # CSS background-image in style attribute
        if tag.has_attr("style"):
            st = tag["style"]
            if "url(" in st:
                # naive replace of url(...)
                import re
                def repl(m):
                    inner = m.group(1).strip(' \'"')
                    new = rewrite_attr(url, inner)
                    return f'url("{new}")' if new else ""
                st2 = re.sub(r'url\(([^)]+)\)', repl, st, flags=re.I)
                tag["style"] = st2

    # Remove inline event handlers (onclick etc.) that may trigger popups
    for el in soup.find_all(True):
        for attr in list(el.attrs):
            if attr.startswith("on"):
                try:
                    del el.attrs[attr]
                except:
                    pass

    # Insert a small banner so user knows they are viewing proxied page
    banner = soup.new_tag("div")
    banner.string = "Ad-free proxy view (some dynamic features may be disabled). Return to proxy home."
    banner['style'] = "background:#f6f6f6;padding:8px;border:1px solid #ddd;margin-bottom:10px;font-size:12px"
    soup.body.insert(0, banner) if soup.body else None

    # Return prettified HTML
    return str(soup)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
