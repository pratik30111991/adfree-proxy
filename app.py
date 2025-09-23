from flask import Flask, render_template, request, jsonify
import requests

app = Flask(__name__)

YOUTUBE_API = "https://ytsearch-proxy.onrender.com/api/search?q="  # Example proxy API

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/search")
def search():
    query = request.args.get("q")
    if not query:
        return jsonify({"error": "No query provided"}), 400
    
    # Call proxy API (you can replace with your own)
    try:
        r = requests.get(YOUTUBE_API + query)
        data = r.json()
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
