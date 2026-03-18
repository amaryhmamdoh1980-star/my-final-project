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

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    user_input = request.form.get("message", "")
    image_file = request.files.get("image")
    # קבלת היסטוריית השיחה מהצד של הלקוח
    history_raw = request.form.get("history", "[]")
    try:
        history = json.loads(history_raw)
    except:
        history = []

    # הגדרת המודל - משתמשים ב-2.5 פלאש לפי בקשתך
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={API_KEY}"
    headers = {'Content-Type': 'application/json'}
    
    # הנחיית מערכת חכמה
    system_instruction = """
    אתה 'המורה החכם' - מומחה להוראת גיאוגרפיה והיסטוריה, בדגש על תוכנית הלימודים לבגרות בישראל.
    1. ענה תמיד בשפה שבה פנו אליך (עברית או ערבית).
    2. שמור על הקשר: השתמש בהיסטוריית השיחה כדי לענות על שאלות המשך.
    3. אם נשלחה תמונה (מפה, סלע, מסמך): נתח אותה לעומק בהקשר הלימודי.
    4. הסבר מושגים מורכבים בצורה פשוטה, עם דוגמאות שיעזרו בבחינה.
    """

    # בניית מבנה השיחה עבור Gemini
    contents = []
    # הוספת היסטוריה (רק טקסט לזיכרון)
    for msg in history:
        contents.append({
            "role": "user" if msg['role'] == "user" else "model",
            "parts": [{"text": msg['text']}]
        })

    # הוספת ההודעה הנוכחית עם ההנחיה
    current_user_parts = [{"text": system_instruction + "\n\nהשאלה הנוכחית: " + user_input}]
    
    if image_file:
        image_data = base64.b64encode(image_file.read()).decode('utf-8')
        current_user_parts.append({
            "inline_data": {
                "mime_type": image_file.content_type,
                "data": image_data
            }
        })
    
    contents.append({"role": "user", "parts": current_user_parts})

    payload = {"contents": contents}

    try:
        response = requests.post(url, json=payload, headers=headers)
        data = response.json()

        if response.status_code == 200:
            reply = data['candidates'][0]['content']['parts'][0]['text']
            try:
                db.execute("INSERT INTO history (user_message, bot_message) VALUES (?, ?)", user_input or "מדיה", reply)
            except: pass
            return jsonify({"reply": reply})
        else:
            return jsonify({"reply": f"שגיאה מהמורה: {data.get('error', {}).get('message', 'נסה שוב')}"}), response.status_code
    except Exception as e:
        return jsonify({"reply": f"תקלה בתקשורת: {str(e)}"}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)