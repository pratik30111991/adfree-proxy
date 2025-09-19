from flask import Flask, request, render_template_string
import requests
from bs4 import BeautifulSoup

app = Flask(__name__)

form_html = """
<!DOCTYPE html>
<html>
<head>
    <title>Ad-Free Proxy</title>
</head>
<body style="font-family: Arial; margin:50px;">
    <h2>Enter Site Name</h2>
    <form method="POST">
        <input type="text" name="site" placeholder="https://example.com" size="50" required>
        <button type="submit">Submit</button>
        <button type="reset">Clear</button>
    </form>
    <hr>
    {% if content %}
        <h3>Ad-Free View:</h3>
        <div style="border:1px solid #ccc; padding:10px; white-space: pre-wrap;">
            {{ content|safe }}
        </div>
    {% endif %}
</body>
</html>
"""

@app.route("/", methods=["GET", "POST"])
def index():
    content = ""
    if request.method == "POST":
        url = request.form.get("site")
        try:
            resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
            soup = BeautifulSoup(resp.text, "html.parser")

            # Remove ads: scripts, iframes, ad tags
            for tag in soup(["script", "iframe", "ins"]):
                tag.decompose()

            content = soup.prettify()
        except Exception as e:
            content = f"Error: {str(e)}"

    return render_template_string(form_html, content=content)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
