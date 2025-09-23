from flask import Flask, request, jsonify
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote_plus

app = Flask(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36"
}

def youtube_search(query, max_results=5):
    query_string = quote_plus(query)
    url = f"https://www.youtube.com/results?search_query={query_string}"

    response = requests.get(url, headers=HEADERS)
    if response.status_code != 200:
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    results = []

    # YouTube page me initial data JSON me hota hai
    for video in soup.find_all("a", href=True):
        href = video['href']
        title = video.get('title')
        if href.startswith("/watch") and title:
            video_url = "https://www.youtube.com" + href
            results.append({"title": title, "url": video_url})
        if len(results) >= max_results:
            break
    return results

@app.route("/search")
def search():
    q = request.args.get("q")
    if not q:
        return jsonify({"error": "Query parameter 'q' missing"}), 400
    results = youtube_search(q)
    return jsonify({"query": q, "results": results})

@app.route("/")
def home():
    return """
    <h2>YouTube Search Proxy is running!</h2>
    <p>Use endpoint: /search?q=YOUR_QUERY</p>
    """

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
