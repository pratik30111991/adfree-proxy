# app.py
from flask import Flask, request, jsonify
import requests
from bs4 import BeautifulSoup

app = Flask(__name__)

BASE_URL = "https://wapking.sbs"

def search_songs(query):
    results = []
    search_url = f"{BASE_URL}/search.php?q={query.replace(' ', '+')}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }
    try:
        r = requests.get(search_url, headers=headers, timeout=10)
        soup = BeautifulSoup(r.text, 'html.parser')
        items = soup.select("div.list div.item a")  # adjust according to site
        for item in items:
            title = item.text.strip()
            url = item['href']
            if not url.startswith("http"):
                url = BASE_URL + url
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
