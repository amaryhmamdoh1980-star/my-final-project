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

IMAGE_WORDS = ["מפה", "מפת", "צייר", "תמונה", "תראה לי", "תצלום", "איור"]

HE_TO_EN = {
    "תראה לי את": "", "תראה לי": "",
    "צייר לי": "", "צייר": "",
    "תמונה של": "", "תמונה": "",
    "מפה של": "map", "מפת": "map", "מפה": "map",
    "תצלום של": "", "תצלום": "",
    "איור של": "", "איור": "",
    "של": "", "את": "", "לי": "", "אז": "",
    "ישראל": "Israel", "ירושלים": "Jerusalem", "תל אביב": "Tel Aviv",
    "חיפה": "Haifa", "אילת": "Eilat", "הנגב": "Negev",
    "הגליל": "Galilee", "הכרמל": "Carmel", "הירדן": "Jordan River",
    "ים המלח": "Dead Sea", "כנרת": "Sea of Galilee",
    "ים התיכון": "Mediterranean Sea", "ים סוף": "Red Sea",
    "הר": "mountain", "מדבר": "desert", "יער": "forest",
    "חוף": "beach", "נהר": "river", "אגם": "lake", "עיר": "city",
    "סלע דולומיט": "dolomite rock", "דולומיט": "dolomite rock",
    "אבן גיר": "limestone rock", "גיר": "limestone",
    "בזלת": "basalt rock", "גרניט": "granite rock",
    "סלע": "rock", "אבן": "stone", "סלעים": "rocks",
    "מינרל": "mineral", "קריסטל": "crystal quartz",
    "דינוזאור": "dinosaur", "פיל": "elephant", "אריה": "lion",
    "נשר": "eagle", "כריש": "shark", "עץ": "tree", "פרח": "flower",
    "שמש": "sun", "ירח": "moon", "אש": "fire", "מים": "water",
}

def translate_to_english(text):
    result = text
    for heb, eng in HE_TO_EN.items():
        result = result.replace(heb, eng)
    result = re.sub(r'\s+', ' ', result).strip()
    if re.search(r'[\u0590-\u05FF]', result):
        result = re.sub(r'[\u0590-\u05FF]+', '', result)
        result = re.sub(r'\s+', ' ', result).strip()
    if not result:
        result = "nature"
    return result

def get_wikimedia_image(query):
    """מחזיר תמונה אמיתית מ-Wikimedia Commons"""
    try:
        url = "https://en.wikipedia.org/w/api.php"
        params = {
            "action": "query",
            "list": "search",
            "srsearch": query,
            "srnamespace": "6",  # File namespace
            "srlimit": "5",
            "format": "json"
        }
        res = requests.get(url, params=params, timeout=8)
        data = res.json()
        results = data.get("query", {}).get("search", [])
        
        for item in results:
            title = item.get("title", "")
            if title.startswith("File:") and any(
                ext in title.lower() for ext in [".jpg", ".jpeg", ".png"]
            ):
                # קבל את ה-URL של הקובץ
                file_params = {
                    "action": "query",
                    "titles": title,
                    "prop": "imageinfo",
                    "iiprop": "url",
                    "format": "json"
                }
                file_res = requests.get(url, params=file_params, timeout=8)
                file_data = file_res.json()
                pages = file_data.get("query", {}).get("pages", {})
                for page in pages.values():
                    imageinfo = page.get("imageinfo", [])
                    if imageinfo:
                        img_url = imageinfo[0].get("url", "")
                        if img_url:
                            print(f"[DEBUG] Wikimedia image: {img_url}")
                            return img_url
    except Exception as e:
        print(f"[DEBUG] Wikimedia error: {e}")
    
    # גיבוי — Unsplash
    encoded = requests.utils.quote(query)
    return f"https://source.unsplash.com/1024x768/?{encoded}"

def build_image_url(user_input):
    english_query = translate_to_english(user_input)
    print(f"[DEBUG] translated: '{user_input}' → '{english_query}'")
    return get_wikimedia_image(english_query)

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

    wants_image = any(word in user_input for word in IMAGE_WORDS)
    image_url = build_image_url(user_input) if wants_image else None

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
        else:
            reply = "הנה התמונה שביקשת:" if wants_image else "שגיאת שרת גוגל."
            print(f"[DEBUG] Gemini error {response.status_code}")

        try:
            db.execute("INSERT INTO history (user_message, bot_message) VALUES (?, ?)", user_input or "תמונה", reply)
        except: pass

        return jsonify({"reply": reply, "image_url": image_url})

    except Exception as e:
        reply = "הנה התמונה שביקשת:" if wants_image else f"תקלה: {str(e)}"
        return jsonify({"reply": reply, "image_url": image_url})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)