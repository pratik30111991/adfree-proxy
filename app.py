from flask import Flask, render_template, request, jsonify
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import time

app = Flask(__name__)

def youtube_search(query, max_results=10):
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    
    driver = webdriver.Chrome(options=options)
    search_url = f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}"
    driver.get(search_url)
    time.sleep(3)  # wait for JS content to load
    
    soup = BeautifulSoup(driver.page_source, "html.parser")
    driver.quit()
    
    results = []
    for video in soup.find_all('a', href=True):
        href = video['href']
        if '/watch?v=' in href:
            video_id = href.split('v=')[1].split('&')[0]
            title = video.get('title') or video.get('aria-label') or video.text.strip()
            if title:
                thumbnail = f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"
                results.append({
                    "title": title,
                    "videoId": video_id,
                    "thumbnail": thumbnail
                })
    
    seen = set()
    unique_results = []
    for r in results:
        if r['videoId'] not in seen:
            unique_results.append(r)
            seen.add(r['videoId'])
    
    return unique_results[:max_results]

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
