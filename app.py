# app.py
from flask import Flask, request, jsonify
import requests
from bs4 import BeautifulSoup

app = Flask(__name__)

YOUTUBE_SEARCH_URL = "https://www.youtube.com/results"

@app.route("/")
def home():
    return "YouTube Search Proxy is running!\nUse endpoint: /search?q=YOUR_QUERY"

@app.route("/search")
def search():
    query = request.args.get("q")
    if not query:
        return jsonify({"error": "Missing query parameter"}), 400

    # YouTube search request
    params = {"search_query": query}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36"
    }

    response = requests.get(YOUTUBE_SEARCH_URL, params=params, headers=headers)
    if response.status_code != 200:
        return jsonify({"error": "Failed to fetch YouTube"}), 500

    # Parse results
    soup = BeautifulSoup(response.text, "html.parser")
    results = []

    for a in soup.find_all("a", href=True):
        href = a['href']
        if "/watch?v=" in href:
            title = a.get("title")
            if not title:
                continue
            video_url = "https://www.youtube.com" + href
            results.append({"title": title, "url": video_url})

    # Remove duplicates
    seen = set()
    unique_results = []
    for r in results:
        if r["url"] not in seen:
            unique_results.append(r)
            seen.add(r["url"])

    return jsonify({"query": query, "results": unique_results[:10]})  # top 10 results

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
