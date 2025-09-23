from flask import Flask, request, jsonify, render_template
import yt_dlp

app = Flask(__name__)

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/search")
def search():
    query = request.args.get("q")
    if not query:
        return jsonify({"error": "Missing query parameter ?q="}), 400

    ydl_opts = {
        "quiet": True,
        "extract_flat": "in_playlist",   # fast search
        "skip_download": True
    }

    results = []
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            search_url = f"ytsearch10:{query}"  # top 10 results
            info = ydl.extract_info(search_url, download=False)
            if "entries" in info:
                for entry in info["entries"]:
                    results.append({
                        "title": entry.get("title"),
                        "videoId": entry.get("id"),
                        "thumbnail": entry.get("thumbnails", [{}])[-1].get("url"),
                        "url": f"https://www.youtube.com/watch?v={entry.get('id')}"
                    })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({"query": query, "results": results})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
