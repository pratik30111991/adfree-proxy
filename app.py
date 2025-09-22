from flask import Flask, request, jsonify, render_template
import requests
from bs4 import BeautifulSoup

app = Flask(__name__)

BASE_URL = "https://www.wapking.com/site_audios.php"  # Example: Replace with working WapKing URL

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/songs")
def get_songs():
    query = request.args.get("q", "")
    page = request.args.get("page", "1")

    params = {"page": page}
    if query:
        params["q"] = query

    try:
        res = requests.get(BASE_URL, params=params, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(res.text, "html.parser")

        songs = []
        for a in soup.select("a[href*='.mp3']"):
            title = a.text.strip()
            link = a["href"]
            if not link.startswith("http"):
                link = "https://www.wapking.com/" + link.lstrip("/")
            songs.append({"title": title, "url": link})

        return jsonify(songs[:20])  # return first 20 results
    except Exception as e:
        return jsonify([])

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
