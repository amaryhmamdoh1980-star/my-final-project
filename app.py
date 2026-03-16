import os
import requests
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

# --- Gemini API Config ---
API_KEY = os.environ.get("GOOGLE_API_KEY")

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    user_input = request.form.get("message", "")
    if not user_input:
        return jsonify({"reply": "לא נשלחה הודעה"}), 400

    # שימוש במודל 2.5 פלאש כפי שראינו ברשימה שלך
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={API_KEY}"
    
    headers = {'Content-Type': 'application/json'}
    
    payload = {
        "parts": [{"text": f"תנהג כמורה מקצועי לגיאוגרפיה והיסטוריה. ענה על השאלה הבאה באותה שפה שבה היא נשאלה: {user_input}"}]
    }

    try:
        response = requests.post(url, json=payload, headers=headers)
        data = response.json()

        if response.status_code == 200:
            reply = data['candidates'][0]['content']['parts'][0]['text']
            try:
                db.execute("INSERT INTO history (user_message, bot_message) VALUES (?, ?)", user_input, reply)
            except:
                pass
            return jsonify({"reply": reply})
        else:
            # שליפת הודעת שגיאה מפורטת מגוגל
            error_msg = data.get('error', {}).get('message', 'Unknown Error')
            return jsonify({"reply": f"שגיאה מגוגל ({response.status_code}): {error_msg}"}), response.status_code

    except Exception as e:
        return jsonify({"reply": f"תקלה בחיבור: {str(e)}"}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)