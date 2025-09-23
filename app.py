from flask import Flask, request, jsonify
import requests
from bs4 import BeautifulSoup

app = Flask(__name__)

# --- Multi-site scrapers ---
def scrape_wapking(query):
    try:
        url = f"https://www.wapking.asia/search/{query.replace(' ', '-')}/"
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        songs = []
        for item in soup.select("div.song > a"):
            title = item.text.strip()
            link = item.get("href")
            if link.startswith("/"):
                link = "https://www.wapking.asia" + link
            songs.append({"title": title, "link": link})
        return songs
    except Exception as e:
        return []

def scrape_jiosaavn(query):
    try:
        url = f"https://www.jiosaavn.com/search/{query.replace(' ', '%20')}"
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        songs = []
        for item in soup.select("a[data-type='song']"):
            title = item.get("title")
            link = item.get("href")
            songs.append({"title": title, "link": link})
        return songs
    except Exception as e:
        return []

# Add more site scrapers if needed

# --- Main search endpoint ---
@app.route("/search")
def search():
    query = request.args.get("q", "")
    if not query:
        return jsonify({"error": "Query parameter 'q' missing"}), 400

    result = []
    # Call each scraper
    result += scrape_wapking(query)
    result += scrape_jiosaavn(query)
    # You can add more scrapers here

    return jsonify(result)

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
