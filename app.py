import os
import requests
import base64
import json
import re
import hashlib
from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text

app = Flask(__name__)

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

MAP_WORDS   = ["מפה", "מפת"]
IMAGE_WORDS = ["צייר", "תמונה", "תראה לי", "תצלום", "איור"]

HE_TO_EN = {
    "תראה לי את": "", "תראה לי": "",
    "צייר לי": "", "צייר": "",
    "תמונה של": "", "תמונה": "",
    "מפה של": "", "מפת": "", "מפה": "",
    "תצלום של": "", "תצלום": "",
    "איור של": "", "איור": "",
    "של": "", "את": "", "לי": "", "אז": "",
    "ישראל": "Israel", "ירושלים": "Jerusalem", "תל אביב": "Tel Aviv",
    "חיפה": "Haifa", "אילת": "Eilat", "הנגב": "Negev",
    "הגליל": "Galilee", "הכרמל": "Carmel",
    "ים המלח": "Dead Sea", "כנרת": "Sea of Galilee",
    "ים התיכון": "Mediterranean Sea", "ים סוף": "Red Sea",
    "הר": "mountain", "מדבר": "desert", "יער": "forest",
    "חוף": "beach", "נהר": "river", "אגם": "lake",
    "שיש": "marble rock", "מרמור": "marble",
    "סלע דולומיט": "dolomite rock", "דולומיט": "dolomite rock",
    "אבן גיר": "limestone rock", "גיר": "limestone",
    "בזלת": "basalt rock", "גרניט": "granite rock",
    "סלע": "rock", "אבן": "stone", "מינרל": "mineral",
    "קריסטל": "crystal quartz", "זהב": "gold mineral",
    "כסף": "silver mineral", "נחושת": "copper mineral",
    "דינוזאור": "dinosaur", "פיל": "elephant",
    "אריה": "lion", "נשר": "eagle", "כריש": "shark",
    "עץ": "tree", "פרח": "flower", "ורד": "rose",
    "שמש": "sun", "ירח": "moon", "אש": "fire",
}

def translate_to_english(text):
    result = text
    for heb, eng in HE_TO_EN.items():
        result = result.replace(heb, eng)
    result = re.sub(r'\s+', ' ', result).strip()
    if re.search(r'[\u0590-\u05FF]', result):
        result = re.sub(r'[\u0590-\u05FF]+', '', result)
        result = re.sub(r'\s+', ' ', result).strip()
    return result.strip() or "nature"

def get_wikipedia_image(query):
    try:
        search_url = "https://en.wikipedia.org/w/api.php"
        search_params = {
            "action": "query",
            "list": "search",
            "srsearch": query,
            "srlimit": 3,
            "format": "json"
        }
        search_res = requests.get(search_url, params=search_params, timeout=6,
                                  headers={"User-Agent": "SmartTeacher/1.0"})
        results = search_res.json().get("query", {}).get("search", [])
        if not results:
            return None

        page_title = results[0]["title"]
        image_params = {
            "action": "query",
            "titles": page_title,
            "prop": "pageimages",
            "pithumbsize": 1000,
            "format": "json"
        }
        img_res = requests.get(search_url, params=image_params, timeout=6,
                               headers={"User-Agent": "SmartTeacher/1.0"})
        pages = img_res.json().get("query", {}).get("pages", {})
        for page in pages.values():
            img_url = page.get("thumbnail", {}).get("source", "")
            if img_url:
                print(f"[DEBUG] Wikipedia image: {img_url}")
                return img_url
    except Exception as e:
        print(f"[DEBUG] Wikipedia error: {e}")
    return None

def build_image_url(user_input):
    is_map = any(word in user_input for word in MAP_WORDS)
    english_query = translate_to_english(user_input)

    # מפה — הוסף "map" לחיפוש כדי לקבל מפה ולא דגל
    if is_map:
        english_query = english_query + " map geography"

    print(f"[DEBUG] translated: '{user_input}' → '{english_query}'")
    img_url = get_wikipedia_image(english_query)
    if img_url:
        return img_url
    seed = int(hashlib.md5(english_query.encode()).hexdigest()[:8], 16) % 1000
    return f"https://picsum.photos/seed/{seed}/1024/768"

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

    wants_visual = any(word in user_input for word in MAP_WORDS + IMAGE_WORDS)
    image_url = build_image_url(user_input) if wants_visual else None

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={API_KEY}"
    headers = {'Content-Type': 'application/json'}

    if wants_visual:
        prompt_text = f"""אתה 'המורה החכם' - פרופסור ומדען מומחה. ענה תמיד ברמה אקדמית גבוהה.
המשתמש ביקש תמונה/מפה — המערכת כבר מטפלת בהצגתה אוטומטית.
תפקידך: ספק תיאור אקדמי מפורט ומעניין של הנושא. אל תזכיר שאינך יכול להציג תמונות.
השאלה: {user_input}"""
    else:
        prompt_text = f"""אתה 'המורה החכם' - פרופסור ומדען מומחה. ענה תמיד ברמה אקדמית גבוהה.
השאלה: {user_input}"""

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
        else:
            reply = "הנה התמונה שביקשת:" if wants_visual else "שגיאת שרת גוגל."
        try:
            db.execute("INSERT INTO history (user_message, bot_message) VALUES (?, ?)", user_input or "תמונה", reply)
        except: pass
        return jsonify({"reply": reply, "image_url": image_url})
    except Exception as e:
        reply = "הנה התמונה שביקשת:" if wants_visual else f"תקלה: {str(e)}"
        return jsonify({"reply": reply, "image_url": image_url})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)