from flask import Flask, render_template, request, jsonify
import requests

app = Flask(__name__)

PIPED_API = "https://piped.kavin.rocks/api/v1"  # Piped public instance

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/get_video", methods=["POST"])
def get_video():
    url = request.json.get("url")
    if not url:
        return jsonify({"error": "No URL provided"}), 400

    # Extract video ID
    if "watch?v=" in url:
        video_id = url.split("watch?v=")[-1].split("&")[0]
    else:
        video_id = url

    # Fetch video info from Piped
    api_url = f"{PIPED_API}/videos/{video_id}"
    resp = requests.get(api_url)
    if resp.status_code != 200:
        return jsonify({"error": "Video not found"}), 404

    return jsonify(resp.json())

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)
