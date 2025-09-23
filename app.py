from flask import Flask, request, jsonify, render_template
import requests
from bs4 import BeautifulSoup

app = Flask(__name__)

BASE_URL = "https://wapking.sbs"
HEADERS = {"User-Agent": "Mozilla/5.0"}

def search_songs(query):
    results = []
    search_url = f"{BASE_URL}/search.php?q={query.replace(' ', '+')}"
    try:
        r = requests.get(search_url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")

        # Get song page links
        items = soup.select("div.list div.item a")
        for item in items[:10]:
            title = item.get_text(strip=True)
            page_url = item.get("href")
            if not page_url.startswith("http"):
                page_url = BASE_URL + page_url

            # Open song page to extract actual audio url
            try:
                r2 = requests.get(page_url, headers=HEADERS, timeout=10)
                s2 = BeautifulSoup(r2.text, "html.parser")
                audio_tag = s2.find("audio")
                if audio_tag and audio_tag.get("src"):
                    song_url = audio_tag["src"]
                    if not song_url.startswith("http"):
                        song_url = BASE_URL + song_url
                    results.append({"title": title, "url": song_url})
            except:
                continue
    except:
        pass
    return results

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/search")
def search():
    q = request.args.get("q", "")
    if not q:
        return jsonify([])
    data = search_songs(q)
    return jsonify(data)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
