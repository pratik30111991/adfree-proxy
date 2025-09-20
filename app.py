import subprocess
import json
from flask import Flask, request, jsonify, render_template_string

app = Flask(__name__)

HTML_PAGE = """
<!DOCTYPE html>
<html>
<head>
  <title>Ad-Free Player</title>
  <style>
    body { background:#111; color:white; font-family:sans-serif; text-align:center; }
    video { width:80%; margin-top:20px; border:2px solid white; }
    .controls { margin-top:20px; }
    button { padding:10px; margin:5px; font-size:16px; cursor:pointer; }
  </style>
</head>
<body>
  <h2>Ad-Free YouTube Player 🎶</h2>
  <input id="url" type="text" placeholder="Enter YouTube URL" style="width:60%;padding:10px;" />
  <button onclick="loadVideo()">Play</button>

  <div id="player"></div>
  <div class="controls">
    <button onclick="prevVideo()">⬅ Prev</button>
    <button onclick="nextVideo()">Next ➡</button>
  </div>

<script>
let playlist = [];
let currentIndex = 0;

function loadVideo() {
    let url = document.getElementById("url").value;
    fetch("/get_video", {
        method:"POST",
        headers:{ "Content-Type":"application/json" },
        body:JSON.stringify({url:url})
    })
    .then(res=>res.json())
    .then(data=>{
        playlist = data.playlist;
        currentIndex = 0;
        playCurrent();
    });
}

function playCurrent(){
    if(playlist.length === 0) return;
    let v = playlist[currentIndex];
    document.getElementById("player").innerHTML =
        `<h3>${v.title}</h3>
         <video controls autoplay>
            <source src="${v.url}" type="video/mp4">
         </video>`;
}

function nextVideo(){
    if(currentIndex < playlist.length-1){
        currentIndex++;
        playCurrent();
    }
}

function prevVideo(){
    if(currentIndex > 0){
        currentIndex--;
        playCurrent();
    }
}
</script>
</body>
</html>
"""

@app.route("/")
def home():
    return render_template_string(HTML_PAGE)

@app.route("/get_video", methods=["POST"])
def get_video():
    data = request.get_json()
    url = data.get("url")
    if not url:
        return jsonify({"error": "No URL provided"}), 400

    try:
        # yt-dlp command to fetch best stream + related videos
        cmd = [
            "yt-dlp",
            "-j",               # JSON output
            "--flat-playlist",  # only metadata
            url
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            return jsonify({"error": "yt-dlp failed", "details": result.stderr}), 500

        lines = result.stdout.strip().split("\n")
        playlist = []

        for line in lines[:5]:  # take max 5 items for Next/Prev
            info = json.loads(line)
            # get actual stream URL for each entry
            stream_cmd = [
                "yt-dlp",
                "-f", "best[ext=mp4][height<=720]",
                "-g",  # get direct URL
                f"https://www.youtube.com/watch?v={info['id']}"
            ]
            stream = subprocess.run(stream_cmd, capture_output=True, text=True)
            stream_url = stream.stdout.strip()
            playlist.append({
                "title": info.get("title", "Untitled"),
                "id": info["id"],
                "url": stream_url
            })

        return jsonify({"playlist": playlist})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
