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

# --- Gemini API Config (Direct Call) ---
API_KEY = os.environ.get("GOOGLE_API_KEY")

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    user_input = request.form.get("message", "")
    if not user_input:
        return jsonify({"reply": "לא נשלחה הודעה"}), 400

    # קריאה ישירה ל-API של גוגל ללא הספרייה הבעייתית
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={API_KEY}"
    
    payload = {
        "contents": [{
            "parts": [{"text": f"ענה כמורה לגיאוגרפיה והיסטוריה בעברית: {user_input}"}]
        }]
    }

    try:
        response = requests.post(url, json=payload)
        response_data = response.json()

        if response.status_code == 200:
            reply = response_data['candidates'][0]['content']['parts'][0]['text']
        else:
            # אם יש שגיאה מגוגל, ננסה להבין מה היא
            error_msg = response_data.get('error', {}).get('message', 'שגיאה לא ידועה')
            return jsonify({"reply": f"שגיאה מהשרת של גוגל: {error_msg}"}), response.status_code

        # שמירה במסד נתונים
        try:
            db.execute("INSERT INTO history (user_message, bot_message) VALUES (?, ?)", user_input, reply)
        except:
            pass

        return jsonify({"reply": reply})

    except Exception as e:
        return jsonify({"reply": f"תקלה בתקשורת: {str(e)}"}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)