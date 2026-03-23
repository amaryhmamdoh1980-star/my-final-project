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

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={API_KEY}"
    headers = {'Content-Type': 'application/json'}

    contents = []
    for msg in history:
        role = "user" if msg['role'] == "user" else "model"
        contents.append({"role": role, "parts": [{"text": msg['text']}]})

    current_parts = [{"text": user_input}]
    if image_file:
        try:
            img_data = base64.b64encode(image_file.read()).decode('utf-8')
            current_parts.append({"inline_data": {"mime_type": image_file.content_type, "data": img_data}})
        except: pass

    contents.append({"role": "user", "parts": current_parts})

    system_instruction = {
        "parts": [{"text": """אתה 'המורה החכם' - פרופסור ומדען מומחה. ענה תמיד ברמה אקדמית גבוהה.

חוק חובה ומוחלט: אם המשתמש מבקש מפה, תמונה, ציור, או כתב "תראה לי" - 
חובה לסיים את התשובה בתגית זו בדיוק, בשורה נפרדת:
[IMAGE_KEYWORD: תיאור מפורט באנגלית של מה לצייר]

דוגמאות:
- "צור לי מפה של ישראל" → [IMAGE_KEYWORD: detailed map of Israel showing cities borders and geography]
- "תראה לי תמונה של אבן גיר" → [IMAGE_KEYWORD: limestone rock sample close up geology]
- "צייר לי דינוזאור" → [IMAGE_KEYWORD: realistic dinosaur illustration Tyrannosaurus Rex]

אם אין בקשה לתמונה/מפה — אל תכתוב את התגית כלל."""}]
    }

    try:
        response = requests.post(url, json={
            "system_instruction": system_instruction,
            "contents": contents
        }, headers=headers)
        data = response.json()
        if response.status_code == 200:
            reply = data['candidates'][0]['content']['parts'][0]['text']
            
            image_url = None
            # חילוץ תגית מהמודל
            match = re.search(r"\[IMAGE_KEYWORD:\s*(.*?)\]", reply, re.IGNORECASE)
            if match:
                keyword = match.group(1).strip()
                reply = re.sub(r"\[IMAGE_KEYWORD:.*?\]", "", reply).strip()
                image_url = f"https://image.pollinations.ai/prompt/{requests.utils.quote(keyword)}?width=1024&height=768&nologo=true"

            # מנגנון גיבוי משופר עם תרגום לאנגלית
            if not image_url and any(word in user_input for word in ["מפה", "צייר", "תראה לי", "תמונה"]):
                translations = {
                    "מפה של": "detailed map of",
                    "מפה": "detailed map of",
                    "צייר לי": "illustration of",
                    "תמונה של": "photo of",
                    "תראה לי": "image of"
                }
                fallback_term = user_input
                for heb, eng in translations.items():
                    fallback_term = fallback_term.replace(heb, eng)
                image_url = f"https://image.pollinations.ai/prompt/{requests.utils.quote(fallback_term)}?width=1024&height=768&nologo=true"

            try:
                db.execute("INSERT INTO history (user_message, bot_message) VALUES (?, ?)", user_input or "תמונה", reply)
            except: pass
            
            return jsonify({"reply": reply, "image_url": image_url})
        return jsonify({"reply": "שגיאת שרת גוגל."}), response.status_code
    except Exception as e:
        return jsonify({"reply": f"תקלה: {str(e)}"}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)