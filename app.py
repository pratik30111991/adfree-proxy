from flask import Flask, render_template, request, jsonify
import requests
from bs4 import BeautifulSoup

app = Flask(__name__)

def youtube_search(query):
    query = query.replace(' ', '+')
    url = f"https://www.youtube.com/results?search_query={query}"
    headers = {
        "User-Agent": "Mozilla/5.0"
    }
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, "html.parser")
    results = []

    for video in soup.find_all('a', href=True):
        href = video['href']
        if '/watch?v=' in href:
            video_id = href.split('v=')[1].split('&')[0]
            title = video.get('title')
            if title:
                thumbnail = f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"
                results.append({
                    "title": title,
                    "videoId": video_id,
                    "thumbnail": thumbnail
                })
    # Remove duplicates
    seen = set()
    unique_results = []
    for r in results:
        if r['videoId'] not in seen:
            unique_results.append(r)
            seen.add(r['videoId'])
    return unique_results[:10]  # top 10 results

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/search')
def search():
    q = request.args.get('q', '')
    if not q:
        return jsonify([])
    results = youtube_search(q)
    return jsonify(results)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
