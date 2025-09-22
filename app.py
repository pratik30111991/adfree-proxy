# app.py
from flask import Flask, request, jsonify
import requests
from bs4 import BeautifulSoup

app = Flask(__name__)

# Popular categories hardcoded (working)
CATEGORIES = [
    {"title": "A To Z Bollywood Mp3 Songs", "url": "https://wapking.sbs/categorylist/44/a_to_z_bollywood_mp3_songs/default/1"},
    {"title": "Hindi Mp3 Songs", "url": "https://wapking.sbs/categorylist/4960/hindi_mp3_songs/default/1"},
    {"title": "Punjabi Mp3 Song", "url": "https://wapking.sbs/categorylist/4554/punjabi_mp3_song/default/1"},
    {"title": "Special Mp3 Songs", "url": "https://wapking.sbs/filelist/3376/special_mp3_songs/new2old/1"}
]

@app.route('/search')
def search():
    artist = request.args.get('q', '').lower()
    results = []

    for cat in CATEGORIES:
        try:
            r = requests.get(cat["url"], timeout=10)
            soup = BeautifulSoup(r.text, "html.parser")
            songs = soup.select("a.song")  # Correct selector depends on site structure
            for s in songs:
                title = s.text.strip()
                link = s.get("href")
                if artist in title.lower():
                    results.append({"title": title, "url": link})
        except Exception as e:
            print(f"Error fetching {cat['url']}: {e}")

    return jsonify(results)

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=10000)
