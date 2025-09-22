from flask import Flask, request, jsonify
import requests
from bs4 import BeautifulSoup

app = Flask(__name__)

BASE_URL = "https://wapking.sbs"

@app.route("/")
def home():
    return "Ad-Free Music Proxy is Running 🎶"

@app.route("/search")
def search():
    query = request.args.get("q")
    if not query:
        return jsonify({"error": "No query provided"}), 400

    try:
        # Wapking search page
        url = f"{BASE_URL}/site_search.php?query={query.replace(' ', '+')}"
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=10)

        if resp.status_code != 200:
            return jsonify([])

        soup = BeautifulSoup(resp.text, "html.parser")
        results = []

        # Example: find all links with MP3
        for link in soup.find_all("a", href=True):
            href = link["href"]
            text = link.get_text(strip=True)
            if "mp3" in href.lower():  # mp3 link filter
                if not href.startswith("http"):
                    href = BASE_URL + href
                results.append({
                    "title": text,
                    "url": href
                })

        return jsonify(results[:20])  # first 20 results only

    except Exception as e:
        return jsonify({"error": str(e)})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
