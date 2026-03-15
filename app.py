import os
import requests
import base64
from flask import Flask, render_template, request, jsonify
from cs50 import SQL

app = Flask(__name__)
db = SQL("postgresql://postgres.yimsexytrswzamnslgcd:MaAm%40036355972@aws-1-ap-northeast-1.pooler.supabase.com:6543/postgres?sslmode=require")

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    user_input = request.form.get("message", "")
    image_file = request.files.get("image")
    api_key = os.environ.get("GOOGLE_API_KEY")
    parts = [{"text": f"ענה כמורה לגיאוגרפיה והיסטוריה בעברית. רק טקסט: {user_input}"}]
    if image_file:
        image_data = base64.b64encode(image_file.read()).decode("utf-8")
        parts.append({"inline_data": {"mime_type": image_file.content_type, "data": image_data}})
    try:
        r = requests.post(
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent",
            headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
            json={"contents": [{"parts": parts}]}
        )
        data = r.json()
        if r.status_code == 200:
            reply = data["candidates"][0]["content"]["parts"][0]["text"]
            db.execute("INSERT INTO chats (user_msg, bot_res, lang) VALUES (:u, :r, :l)", u=user_input, r=reply, l="Hebrew")
            return jsonify({"reply": reply})
        else:
            return jsonify({"reply": f"שגיאה: {data.get('error',{}).get('message','')}"})
    except Exception as e:
        return jsonify({"reply": f"שגיאה: {str(e)}"})

@app.route("/history")
def history():
    chats = db.execute("SELECT * FROM chats ORDER BY id DESC")
    return render_template("history.html", chats=chats)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
