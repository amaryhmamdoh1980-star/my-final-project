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
    history_raw = request.form.get("history", "[]")
    
    try:
        history = json.loads(history_raw)
    except:
        history = []

    if not user_input and not image_file:
        return jsonify({"reply": "Empty message"}), 400

    # חזרה לגרסה היציבה ביותר שעובדת בטוח
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={API_KEY}"

    headers = {'Content-Type': 'application/json'}
    
    prompt_text = f"""
    אתה 'המורה החכם' - פרופסור ומדען.
    ענה ברמה אקדמית גבוהה.
    אם המשתמש מבקש לראות מפה או תמונה, סיים את התשובה בפורמט: [IMAGE_KEYWORD: English description]
    
    השאלה: {user_input}
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
    payload = {"contents": contents}

    try:
        response = requests.post(url, json=payload, headers=headers)
        data = response.json()
        
        if response.status_code == 200:
            reply = data['candidates'][0]['content']['parts'][0]['text']
            
            # לוגיקה פשוטה לתמונה
            image_url = None
            if "[IMAGE_KEYWORD:" in reply:
                keyword = reply.split("[IMAGE_KEYWORD:")[1].split("]")[0].strip()
                reply = reply.split("[IMAGE_KEYWORD:")[0].strip()
                image_url = f"https://image.pollinations.ai/prompt/{requests.utils.quote(keyword)}?width=1024&height=1024&model=flux"

            try:
                db.execute("INSERT INTO history (user_message, bot_message) VALUES (?, ?)", user_input or "תמונה", reply)
            except: pass
            
            return jsonify({"reply": reply, "image_url": image_url})
        
        # שינוי קריטי: אם יש שגיאה, נחזיר את ההודעה המקורית מגוגל כדי שנבין למה!
        error_info = data.get('error', {}).get('message', 'Unknown Google Error')
        return jsonify({"reply": f"שגיאת גוגל: {error_info}"}), response.status_code

    except Exception as e:
        return jsonify({"reply": f"תקלה בשרת: {str(e)}"}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)