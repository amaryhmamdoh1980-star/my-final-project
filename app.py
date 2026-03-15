import os
import google.generativeai as genai
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

# --- Gemini Config ---
# ניסיון להגדיר את ה-API בצורה שתמנע את שגיאת ה-v1beta
api_key = os.environ.get("GOOGLE_API_KEY")
genai.configure(api_key=api_key)

# שימוש בשם המודל הפשוט ביותר - הספרייה כבר תדע להוסיף models/
model = genai.GenerativeModel('gemini-1.5-flash')

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    user_input = request.form.get("message", "")
    if not user_input:
        return jsonify({"reply": "לא התקבלה הודעה"}), 400

    try:
        # שליחה למודל
        response = model.generate_content(user_input)
        
        if response and response.text:
            reply = response.text
        else:
            reply = "המערכת לא החזירה תשובה, נסה שוב."

        # שמירה במסד נתונים
        try:
            db.execute("INSERT INTO history (user_message, bot_message) VALUES (?, ?)", user_input, reply)
        except:
            pass # התעלמות משגיאת דאטהבייס כדי שהצ'אט ימשיך לעבוד

        return jsonify({"reply": reply})

    except Exception as e:
        print(f"Detailed Error: {str(e)}")
        # אם יש שגיאה, נחזיר הודעה ברורה למשתמש
        return jsonify({"reply": f"שגיאה בחיבור למודל: {str(e)}"}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)