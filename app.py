from flask import Flask, render_template, request, jsonify
import yt_dlp

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/search')
def search():
    query = request.args.get('q')
    if not query:
        return jsonify({"error": "Query parameter missing!"}), 400

    ydl_opts = {
        'quiet': True,
        'skip_download': True,
        'extract_flat': True,
        'forcejson': True,
    }

    search_results = []
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch10:{query}", download=False)
            for entry in info.get('entries', []):
                search_results.append({
                    'title': entry.get('title'),
                    'videoId': entry.get('id'),
                    'thumbnail': entry.get('thumbnail'),
                    'url': f"https://www.youtube.com/watch?v={entry.get('id')}"
                })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({"query": query, "results": search_results})

@app.route('/play')
def play():
    video_id = request.args.get('videoId')
    if not video_id:
        return jsonify({"error": "videoId missing!"}), 400

    ydl_opts = {
        'format': 'bestaudio/best',
        'quiet': True
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
            audio_url = info['url']
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({"videoId": video_id, "audio_url": audio_url})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=10000)
