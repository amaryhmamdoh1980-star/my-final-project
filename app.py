import os
import google.generativeai as genai
from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text

app = Flask(__name__)

# --- הגדרת מסד הנתונים (SQLAlchemy) ---
# שימוש בכתובת ה-Supabase שלך מהתמונות הקודמות
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres.yimsexytrswzamnslgcd:MaAm%40036355972@aws-0-ap-northeast-1.pooler.supabase.com:6543/postgres'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db_obj = SQLAlchemy(app)

# אובייקט עזר לשמירה על תאימות לפקודות db.execute שאתה מכיר
class DB:
    def execute(self, query, *args):
        # המרת סימני שאלה לפורמט של SQLAlchemy (:val0, :val1...)
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

# --- הגדרת Gemini SDK ---
genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))
model = genai.GenerativeModel('gemini-1.5-flash')

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    user_input = request.form.get("message", "")
    
    if not user_input:
        return jsonify({"error": "No message provided"}), 400

    try:
        # שליחת הודעה ל-Gemini באמצעות ה-SDK
        prompt = f"ענה כמורה לגיאוגרפיה והיסטוריה בעברית. רק טקסט: {user_input}"
        response = model.generate_content(prompt)
        reply = response.text
        
        # שמירת ההיסטוריה במסד הנתונים
        db.execute("INSERT INTO history (user_message, bot_message) VALUES (?, ?)", user_input, reply)
        
        return jsonify({"reply": reply})
    
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"error": "משהו השתבש בתקשורת עם המודל"}), 500

if __name__ == "__main__":
    app.run(debug=True)