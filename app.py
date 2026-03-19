import os
import requests
import base64
import json
from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text

app = Flask(__name__)

# --- Database Setup ---
DB_URL = os.environ.get('DATABASE_URL', 'postgresql://postgres.yimsexytrswzamnslgcd:MaAm%40036355972@aws-0-ap-northeast-1.pooler.supabase.com:6543/postgres')
app.config['SQLALCHEMY_DATABASE_URI'] = DB_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db_obj = SQLAlchemy(app)

class DB:
    def execute(self, query, *args):
        formatted_query = query
        params = {}
        for i, arg in enumerate(args):
            placeholder = f"val{i}"
            formatted_query = formatted_query.replace("?", f":{placeholder}", 1)
            params[placeholder] = arg
        result = db_obj.session.execute(text(formatted_query), params)
        db_obj.session.commit()
        if query.strip().upper().startswith("SELECT"):
            return [dict(row._mapping) for row in result]
        return None

db = DB()
API_KEY = os.environ.get("GOOGLE_API_KEY")

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    user_input = request.form.get("message", "")
    image_file = request.files.get("image")
    history_raw = request.form.get("history", "[]")
    history = json.loads(history_raw)

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={API_KEY}"
    headers = {'Content-Type': 'application/json'}
    
    prompt_text = f"""
    אתה 'המורה החכם' - מומחה לגיאוגרפיה והיסטוריה.
    
    חוק לתמונות:
    אם המשתמש מבקש לראות סלע, צמח, או נוף, הוסף בתחתית התשובה שורה כזו:
    ![image](https://loremflickr.com/600/400/{user_input},rock/all)
    (וודא שהמילה 'rock' נשארת בתוך הקישור כדי לסנן תמונות רלוונטיות).
    
    ענה תמיד בשפה שבה פנו אליך.
    השאלה: {user_input}
    """   

    contents = []
    for msg in history:
        contents.append({"role": "user" if msg['role'] == "user" else "model", "parts": [{"text": msg['text']}]})

    current_parts = [{"text": prompt_text}]
    if image_file:
        image_data = base64.b64encode(image_file.read()).decode('utf-8')
        current_parts.append({"inline_data": {"mime_type": image_file.content_type, "data": image_data}})
    
    contents.append({"role": "user", "parts": current_parts})
    payload = {"contents": contents}

    try:
        response = requests.post(url, json=payload, headers=headers)
        data = response.json()
        if response.status_code == 200:
            reply = data['candidates'][0]['content']['parts'][0]['text']
            try: db.execute("INSERT INTO history (user_message, bot_message) VALUES (?, ?)", user_input or "מדיה", reply)
            except: pass
            return jsonify({"reply": reply})
        return jsonify({"reply": "שגיאה מהמורה."}), response.status_code
    except Exception as e:
        return jsonify({"reply": f"תקלה: {str(e)}"}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)