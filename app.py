from flask import Flask, request, jsonify
import requests
from bs4 import BeautifulSoup

app = Flask(__name__)

BASE_URL = "https://wapking.sbs"

def search_songs(query):
    results = []
    # Wapking search URL
    search_url = f"{BASE_URL}/search?q={query.replace(' ', '+')}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }
    try:
        r = requests.get(search_url, headers=headers, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")

        # Pick results from Google Custom Search overlay
        items = soup.select(".gsc-webResult .gs-title a")

        for item in items:
            title = item.get_text(strip=True)
            url = item.get("href")
            if not url:
                continue
            results.append({"title": title, "url": url})
    except Exception as e:
        print("Error:", e)
    return results

@app.route("/search")
def search():
    q = request.args.get("q", "")
    if not q:
        return jsonify([])
    data = search_songs(q)
    return jsonify(data)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
