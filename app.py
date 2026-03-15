import os
import google.generativeai as genai
from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text

app = Flask(__name__)

# --- הגדרת מסד הנתונים ---
# הקוד ינסה קודם לקחת את הכתובת ממשתנה סביבה (אבטחה), ואם אין - ישתמש בקישור הישיר
DB_URL = os.environ.get('DATABASE_URL', 'postgresql://postgres.yimsexytrswzamnslgcd:MaAm%40036355972@aws-0-ap-northeast-1.pooler.supabase.com:6543/postgres')
app.config['SQLALCHEMY_DATABASE_URI'] = DB_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db_obj = SQLAlchemy(app)

# אובייקט עזר לשמירה על תאימות לפקודות db.execute
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

# --- הגדרת Gemini SDK ---
# הגדרה שתומכת בגרסה היציבה ומונעת שגיאות v1beta
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
        # שליחת הודעה ל-Gemini
        prompt = f"ענה כמורה לגיאוגרפיה והיסטוריה בעברית: {user_input}"
        response = model.generate_content(prompt)
        
        # בדיקה אם התקבלה תשובה תקינה
        if response and response.text:
            reply = response.text
        else:
            reply = "מצטער, המודל לא החזיר תשובה. נסה שוב."
        
        # שמירת ההיסטוריה במסד הנתונים
        try:
            db.execute("INSERT INTO history (user_message, bot_message) VALUES (?, ?)", user_input, reply)
        except Exception as db_err:
            print(f"Database Error: {db_err}")
        
        return jsonify({"reply": reply})
    
    except Exception as e:
        print(f"Error: {e}")
        # מחזירים הודעת שגיאה מפורטת ב-JSON כדי שהצ'אט לא יראה "undefined"
        return jsonify({"reply": f"שגיאה: {str(e)}"}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)