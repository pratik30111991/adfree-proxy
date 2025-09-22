from flask import Flask, render_template, request, jsonify
import requests
from bs4 import BeautifulSoup

app = Flask(__name__)

# Demo streaming site (replace with a legal streaming URL if needed)
STREAM_SITE = "https://wapking.sbs/search/{}"

def fetch_stream_songs(query="", page=1):
    """Fetch songs/videos from a streaming site via scraping"""
    if not query:
        query = "latest"
    url = STREAM_SITE.format(query.replace(" ", "+"))
    results = []

    try:
        resp = requests.get(url, timeout=12)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Parse songs/videos
        items = soup.select(".song-box")  # adjust selector based on site structure
        for item in items:
            title_tag = item.select_one(".title")
            thumb_tag = item.select_one("img")
            link_tag = item.select_one("a")
            if title_tag and link_tag:
                results.append({
                    "title": title_tag.text.strip(),
                    "video_url": link_tag["href"],
                    "thumbnail": thumb_tag["src"] if thumb_tag else "",
                    "sources": { "default": link_tag["href"] }
                })
    except Exception as e:
        print("Error fetching songs:", e)

    return results

@app.route("/songs")
def songs():
    q = request.args.get("q", "")
    page = int(request.args.get("page", 1))
    return jsonify(fetch_stream_songs(query=q, page=page))

@app.route("/")
def index():
    return render_template("index.html")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)
