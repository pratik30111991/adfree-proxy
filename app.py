from flask import Flask, render_template, request, jsonify
import requests
from bs4 import BeautifulSoup
import re

app = Flask(__name__)

BASE_URL = "https://wapking.sbs"

def scrape_wapking(query="", page=1):
    """Scrape WapKing for songs"""
    results = []
    try:
        if query:
            search_url = f"{BASE_URL}/search?query={query}&page={page}"
        else:
            search_url = f"{BASE_URL}/latest?page={page}"

        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(search_url, headers=headers, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Find song blocks
        items = soup.select(".song-item")  # Inspect WapKing HTML for correct class
        for item in items:
            title_tag = item.select_one(".song-title")
            artist_tag = item.select_one(".song-artist")
            link_tag = item.select_one("a")
            img_tag = item.select_one("img")

            if not title_tag or not link_tag:
                continue

            title = title_tag.get_text(strip=True)
            artist = artist_tag.get_text(strip=True) if artist_tag else "Unknown"
            song_page = BASE_URL + link_tag["href"]
            thumbnail = img_tag["src"] if img_tag else ""

            # Get actual audio URL from song page
            try:
                page_resp = requests.get(song_page, headers=headers, timeout=10)
                page_resp.raise_for_status()
                page_soup = BeautifulSoup(page_resp.text, "html.parser")
                audio_tag = page_soup.select_one("audio source")
                audio_url = audio_tag["src"] if audio_tag else ""
            except:
                audio_url = ""

            results.append({
                "title": title,
                "artist": artist,
                "video_url": audio_url,
                "audio_url": audio_url,
                "thumbnail": thumbnail,
                "sources": { "default": audio_url }
            })
    except Exception as e:
        print("Error scraping WapKing:", e)
    return results

@app.route("/songs")
def songs():
    q = request.args.get("q", "").strip()
    page = int(request.args.get("page", 1))
    data = scrape_wapking(query=q, page=page)
    return jsonify(data)

@app.route("/")
def index():
    return render_template("index.html")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)
