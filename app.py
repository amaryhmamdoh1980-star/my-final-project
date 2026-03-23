import os
import requests
import base64
import json
import re
from flask import Flask, render_template, request, jsonify
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

VISUAL_WORDS = ["מפה", "מפת", "צייר", "תמונה", "תראה לי", "תצלום", "איור"]

def build_unsplash_url(user_input):
    """תמונה מ-Unsplash לפי נושא"""
    removals = [
        "מפה של", "מפת", "מפה",
        "צייר לי", "צייר",
        "תמונה של", "תמונה",
        "תראה לי את", "תראה לי",
        "תצלום של", "תצלום",
        "איור של", "איור",
    ]
    query = user_input
    for word in removals:
        query = query.replace(word, "").strip()

    # תרגום מילים נפוצות לאנגלית
    translations = {
        "ישראל": "Israel", "ירושלים": "Jerusalem", "תל אביב": "Tel Aviv",
        "ים": "sea", "הר": "mountain", "מדבר": "desert", "יער": "forest",
        "אבן": "stone", "סלע": "rock", "גיר": "limestone", "חוף": "beach",
        "עיר": "city", "כפר": "village", "נהר": "river", "אגם": "lake",
        "בעל חיים": "animal", "דינוזאור": "dinosaur", "פרח": "flower",
        "עץ": "tree", "שמיים": "sky", "שקיעה": "sunset", "זריחה": "sunrise",
    }
    for heb, eng in translations.items():
        query = query.replace(heb, eng)

    query = query.strip()
    if not query:
        query = "nature"

    encoded = requests.utils.quote(query)
    return f"https://source.unsplash.com/1024x768/?{encoded}"

def ask_gemini(user_input, history, image_file):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={API_KEY}"
    headers = {'Content-Type': 'application/json'}
    prompt_text = f"אתה 'המורה החכם' - פרופסור ומדען מומחה. ענה תמיד ברמה אקדמית גבוהה.\nהשאלה: {user_input}"

    contents = []
    for msg in history:
        role = "user" if msg['role'] == "user" else "model"
        contents.append({"role": role, "parts": [{"text": msg['text']}]})
    contents.append({"role": "user", "parts": [{"text": prompt_text}]})

    if image_file:
        try:
            img_data = base64.b64encode(image_file.read()).decode('utf-8')
            contents[-1]["parts"].append({"inline_data": {"mime_type": image_file.content_type, "data": img_data}})
        except: pass

    response = requests.post(url, json={"contents": contents}, headers=headers)
    data = response.json()
    if response.status_code == 200:
        return data['candidates'][0]['content']['parts'][0]['text'], response.status_code
    return "שגיאת שרת גוגל.", response.status_code

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    user_input = request.form.get("message", "")
    image_file = request.files.get("image")
    history_raw = request.form.get("history", "[]")

    try:
        history = json.loads(history_raw)
    except:
        history = []

    if not user_input and not image_file:
        return jsonify({"reply": "Empty message"}), 400

    wants_visual = any(word in user_input for word in VISUAL_WORDS)
    image_url = build_unsplash_url(user_input) if wants_visual else None

    try:
        reply, status = ask_gemini(user_input, history, image_file)
        if status != 200:
            return jsonify({"reply": reply}), status
        try:
            db.execute("INSERT INTO history (user_message, bot_message) VALUES (?, ?)", user_input or "תמונה", reply)
        except: pass
        return jsonify({"reply": reply, "image_url": image_url})
    except Exception as e:
        return jsonify({"reply": f"תקלה: {str(e)}"}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)