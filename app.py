import os
import requests
import base64
import json
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

IMAGE_WORDS = ["מפה", "מפת", "צייר", "תמונה", "תראה לי", "תצלום", "איור"]

def build_image_url(user_input):
    """בניית URL לתמונה ישירות מהקלט — ללא תלות ב-Gemini"""
    translations = [
        ("מפה של", "map of"),
        ("מפת", "map of"),
        ("מפה", "map of"),
        ("צייר לי", "illustration of"),
        ("צייר", "illustration of"),
        ("תמונה של", "photo of"),
        ("תמונה", "photo of"),
        ("תראה לי את", "image of"),
        ("תראה לי", "image of"),
        ("תצלום של", "photograph of"),
        ("תצלום", "photograph of"),
        ("איור של", "illustration of"),
        ("איור", "illustration of"),
    ]
    result = user_input
    for heb, eng in translations:
        result = result.replace(heb, eng).strip()
    if not result:
        result = "nature"
    print(f"[DEBUG] image keyword: {result}")
    return f"https://image.pollinations.ai/prompt/{requests.utils.quote(result)}?width=1024&height=768&nologo=true"

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

    # בדיקה מיידית לפני Gemini
    wants_image = any(word in user_input for word in IMAGE_WORDS)
    image_url = build_image_url(user_input) if wants_image else None
    print(f"[DEBUG] user_input={user_input!r}, wants_image={wants_image}, image_url={image_url}")

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={API_KEY}"
    headers = {'Content-Type': 'application/json'}

    prompt_text = f"""
    אתה 'המורה החכם' - פרופסור ומדען מומחה.
    ענה תמיד ברמה אקדמית גבוהה.
    השאלה הנוכחית: {user_input}
    """

    contents = []
    for msg in history:
        role = "user" if msg['role'] == "user" else "model"
        contents.append({"role": role, "parts": [{"text": msg['text']}]})

    current_parts = [{"text": prompt_text}]
    if image_file:
        try:
            img_data = base64.b64encode(image_file.read()).decode('utf-8')
            current_parts.append({"inline_data": {"mime_type": image_file.content_type, "data": img_data}})
        except: pass

    contents.append({"role": "user", "parts": current_parts})

    try:
        response = requests.post(url, json={"contents": contents}, headers=headers)
        data = response.json()
        if response.status_code == 200:
            reply = data['candidates'][0]['content']['parts'][0]['text']
            print(f"[DEBUG] gemini reply (first 200): {reply[:200]!r}")
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