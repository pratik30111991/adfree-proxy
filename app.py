from flask import Flask, request, jsonify, render_template_string
import yt_dlp

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
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": False,
            "format": "best[ext=mp4][height<=720]",
        }

        playlist = []
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

            # Agar ye ek playlist hai
            if "entries" in info:
                entries = info["entries"][:5]  # sirf first 5 load karo
                for e in entries:
                    if not e:
                        continue
                    formats = e.get("formats") or []
                    stream_url = None
                    for f in formats:
                        if f.get("ext") == "mp4" and f.get("url"):
                            stream_url = f["url"]
                            break
                    if stream_url:
                        playlist.append({
                            "title": e.get("title"),
                            "id": e.get("id"),
                            "url": stream_url
                        })
            else:
                # Single video
                formats = info.get("formats") or []
                stream_url = None
                for f in formats:
                    if f.get("ext") == "mp4" and f.get("url"):
                        stream_url = f["url"]
                        break
                if stream_url:
                    playlist.append({
                        "title": info.get("title"),
                        "id": info.get("id"),
                        "url": stream_url
                    })

        return jsonify({"playlist": playlist})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
