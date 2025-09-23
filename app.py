from flask import Flask, request, jsonify
import requests
from bs4 import BeautifulSoup

app = Flask(__name__)

@app.route("/search")
def search_song():
    query = request.args.get("q")
    results = []

    # Example: WapKing
    url = f"https://wapking.asia/search?q={query}"
    r = requests.get(url)
    soup = BeautifulSoup(r.text, "html.parser")
    
    # Example parsing (adjust according to site)
    for item in soup.select(".song-list-item"):
        title = item.select_one(".song-title").text
        link = item.select_one("a")["href"]
        results.append({
            "title": title,
            "artist": "",
            "audio_links": [link],
            "source_url": url
        })

    return jsonify(results)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
