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
    "קריסטל": "crystal quartz", "זהב": "gold",
    "כסף": "silver", "נחושת": "copper",
    "דינוזאור": "dinosaur", "פיל": "elephant",
    "אריה": "lion", "נשר": "eagle", "כריש": "shark",
    "עץ": "tree", "פרח": "flower", "ורד": "rose",
    "שמש": "sun", "ירח": "moon", "אש": "fire",
    "צרפת": "France", "גרמניה": "Germany", "ספרד": "Spain",
    "איטליה": "Italy", "יוון": "Greece", "מצרים": "Egypt",
    "ירדן": "Jordan", "סוריה": "Syria", "לבנון": "Lebanon",
    "ארצות הברית": "United States", "אמריקה": "America",
    "רוסיה": "Russia", "סין": "China", "יפן": "Japan",
    "הודו": "India", "ברזיל": "Brazil", "אוסטרליה": "Australia",
    "קנדה": "Canada", "בריטניה": "United Kingdom", "טורקיה": "Turkey",
}

# מילות סינון — תמונות שלא רוצים
BAD_IMAGE_KEYWORDS = [
    "globe", "locator", "orthographic", "location_map",
    "flag", "coat_of_arms", "emblem", "seal", "banner",
    "Flag_of", "Coat_of_arms", "Globe", "Locator"
]

def translate_to_english(text):
    result = text
    for heb, eng in HE_TO_EN.items():
        result = result.replace(heb, eng)
    result = re.sub(r'\s+', ' ', result).strip()
    if re.search(r'[\u0590-\u05FF]', result):
        result = re.sub(r'[\u0590-\u05FF]+', '', result)
        result = re.sub(r'\s+', ' ', result).strip()
    return result.strip() or "nature"

def is_bad_image(url):
    """בודק אם התמונה היא גלובוס/דגל שלא רוצים"""
    return any(bad in url for bad in BAD_IMAGE_KEYWORDS)

def get_page_images(page_title, is_map=False):
    """מחזיר את כל התמונות של ערך Wikipedia ובוחר את הטובה ביותר"""
    try:
        api_url = "https://en.wikipedia.org/w/api.php"
        params = {
            "action": "query",
            "titles": page_title,
            "prop": "images",
            "imlimit": 20,
            "format": "json"
        }
        res = requests.get(api_url, params=params, timeout=6,
                           headers={"User-Agent": "SmartTeacher/1.0"})
        pages = res.json().get("query", {}).get("pages", {})

        image_titles = []
        for page in pages.values():
            for img in page.get("images", []):
                title = img.get("title", "")
                if any(ext in title.lower() for ext in [".jpg", ".jpeg", ".png"]):
                    image_titles.append(title)

        # סינון ובחירה
        map_keywords = ["map", "topograph", "relief", "terrain", "geographic"]
        preferred = []
        fallback = []

        for title in image_titles:
            t_lower = title.lower()
            if is_bad_image(title):
                continue
            if is_map and any(k in t_lower for k in map_keywords):
                preferred.append(title)
            else:
                fallback.append(title)

        candidates = preferred if preferred else fallback
        if not candidates:
            return None

        # קבל URL של התמונה הראשונה המתאימה
        for img_title in candidates[:5]:
            url_params = {
                "action": "query",
                "titles": img_title,
                "prop": "imageinfo",
                "iiprop": "url",
                "iiurlwidth": 1000,
                "format": "json"
            }
            url_res = requests.get(api_url, params=url_params, timeout=6,
                                   headers={"User-Agent": "SmartTeacher/1.0"})
            url_pages = url_res.json().get("query", {}).get("pages", {})
            for p in url_pages.values():
                info = p.get("imageinfo", [])
                if info:
                    img_url = info[0].get("thumburl") or info[0].get("url", "")
                    if img_url and not is_bad_image(img_url):
                        print(f"[DEBUG] Selected image: {img_url}")
                        return img_url
    except Exception as e:
        print(f"[DEBUG] get_page_images error: {e}")
    return None

def get_wikipedia_image(query, is_map=False):
    try:
        api_url = "https://en.wikipedia.org/w/api.php"

        # חיפוש ערך מתאים
        search_query = query + " map" if is_map else query
        search_params = {
            "action": "query",
            "list": "search",
            "srsearch": search_query,
            "srlimit": 5,
            "format": "json"
        }
        search_res = requests.get(api_url, params=search_params, timeout=6,
                                  headers={"User-Agent": "SmartTeacher/1.0"})
        results = search_res.json().get("query", {}).get("search", [])
        if not results:
            return None

        # נסה עד 3 ערכים
        for result in results[:3]:
            page_title = result["title"]
            print(f"[DEBUG] Trying Wikipedia page: {page_title}")

            # נסה קודם thumbnail ישיר
            thumb_params = {
                "action": "query",
                "titles": page_title,
                "prop": "pageimages",
                "pithumbsize": 1000,
                "format": "json"
            }
            thumb_res = requests.get(api_url, params=thumb_params, timeout=6,
                                     headers={"User-Agent": "SmartTeacher/1.0"})
            thumb_pages = thumb_res.json().get("query", {}).get("pages", {})
            for p in thumb_pages.values():
                img_url = p.get("thumbnail", {}).get("source", "")
                if img_url and not is_bad_image(img_url):
                    print(f"[DEBUG] Thumbnail OK: {img_url}")
                    return img_url

            # אם thumbnail רע — חפש בכל תמונות הדף
            img_url = get_page_images(page_title, is_map=is_map)
            if img_url:
                return img_url

    except Exception as e:
        print(f"[DEBUG] Wikipedia error: {e}")
    return None

def build_image_url(user_input):
    is_map = any(word in user_input for word in MAP_WORDS)
    english_query = translate_to_english(user_input)
    print(f"[DEBUG] translated: '{user_input}' → '{english_query}' (map={is_map})")

    img_url = get_wikipedia_image(english_query, is_map=is_map)
    if img_url:
        return img_url

    # גיבוי: Picsum
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