from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

# Sample media library (replace/add more from archive.org or other free sources)
MEDIA_LIBRARY = [
    {
        "title": "Meditation Song 1",
        "artist": "Unknown",
        "year": 2020,
        "category": "devotional",
        "audio_url": "https://archive.org/download/sample-audio/sample1.mp3",
        "video_url": "https://archive.org/download/sample-video/sample1.mp4",
        "qualities": ["144p", "360p", "720p"]
    },
    {
        "title": "Comedy Song 1",
        "artist": "Funny Artist",
        "year": 2018,
        "category": "jokes",
        "audio_url": "https://archive.org/download/sample-audio/sample2.mp3",
        "video_url": "https://archive.org/download/sample-video/sample2.mp4",
        "qualities": ["144p", "360p"]
    },
    {
        "title": "Classic Song 90s",
        "artist": "Old Artist",
        "year": 1995,
        "category": "classic",
        "audio_url": "https://archive.org/download/sample-audio/sample3.mp3",
        "video_url": "https://archive.org/download/sample-video/sample3.mp4",
        "qualities": ["144p", "360p", "720p"]
    }
]

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/search", methods=["GET"])
def search():
    query = request.args.get("q", "").lower()
    category = request.args.get("category", "").lower()
    results = []

    for item in MEDIA_LIBRARY:
        if ((query in item["title"].lower()) or
            (query in item["artist"].lower()) or
            (query in str(item["year"]))) and \
           (category in item["category"].lower() or not category):
            results.append(item)

    return jsonify(results)

@app.route("/default_songs", methods=["GET"])
def default_songs():
    # Return first 5 songs (or fewer if library smaller) as default suggestions
    return jsonify(MEDIA_LIBRARY[:5])

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)
