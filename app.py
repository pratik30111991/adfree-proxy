# app.py
from flask import Flask, request, jsonify
import requests
from bs4 import BeautifulSoup

app = Flask(__name__)

BASE_URL = "https://wapking.sbs"

def get_songs_from_category(cat_url):
    songs = []
    r = requests.get(cat_url)
    soup = BeautifulSoup(r.text, 'html.parser')
    for a in soup.select('div.songname a'):
        title = a.get_text(strip=True)
        url = a['href']
        if not url.startswith('http'):
            url = BASE_URL + url
        songs.append({"title": title, "url": url})
    return songs

@app.route("/search")
def search():
    query = request.args.get("q", "")
    result = []

    # Step 1: fetch categories
    search_url = f"{BASE_URL}/search.php?search={query.replace(' ','+')}"
    r = requests.get(search_url)
    soup = BeautifulSoup(r.text, 'html.parser')

    # Step 2: parse categories
    for cat in soup.select('div.category a'):
        cat_title = cat.get_text(strip=True)
        cat_url = cat['href']
        if not cat_url.startswith('http'):
            cat_url = BASE_URL + cat_url

        # Step 3: parse songs in this category
        songs = get_songs_from_category(cat_url)
        for s in songs:
            result.append(s)

    return jsonify(result)

if __name__ == "__main__":
    app.run(debug=True)
