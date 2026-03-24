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
    "ארצות הברית": "United States", "אמריקה": "United States",
    "רוסיה": "Russia", "סין": "China", "יפן": "Japan",
    "הודו": "India", "ברזיל": "Brazil", "אוסטרליה": "Australia",
    "קנדה": "Canada", "בריטניה": "United Kingdom", "טורקיה": "Turkey",
    "פולין": "Poland", "שוודיה": "Sweden", "נורווגיה": "Norway",
    "אוקראינה": "Ukraine", "איראן": "Iran", "סעודיה": "Saudi Arabia",
}

BAD_KEYWORDS = ["globe", "locator", "orthographic", "Flag_of", "Coat_of",
                 "emblem", "seal", "banner", "logo", "icon", "portrait",
                 "newspaper", "magazine", "article", "stamp"]

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
    return any(bad.lower() in url.lower() for bad in BAD_KEYWORDS)

def search_wikimedia_map(place_name):
    """חיפוש ישיר בקטגוריית מפות של Wikimedia Commons"""
    try:
        api_url = "https://commons.wikimedia.org/w/api.php"
        params = {
            "action": "query",
            "list": "search",
            "srsearch": f"map {place_name} -flag -globe -locator",
            "srnamespace": "6",
            "srlimit": 10,
            "format": "json"
        }
        res = requests.get(api_url, params=params, timeout=6,
                           headers={"User-Agent": "SmartTeacher/1.0"})
        results = res.json().get("query", {}).get("search", [])

        for item in results:
            title = item.get("title", "")
            t_lower = title.lower()
            if not any(ext in t_lower for ext in [".jpg", ".jpeg", ".png", ".svg"]):
                continue
            if is_bad_image(title):
                continue
            if any(k in t_lower for k in ["map", "topograph", "relief", "terrain", "geographic"]):
                # קבל URL
                url_params = {
                    "action": "query",
                    "titles": title,
                    "prop": "imageinfo",
                    "iiprop": "url",
                    "iiurlwidth": 1000,
                    "format": "json"
                }
                url_res = requests.get(api_url, params=url_params, timeout=6,
                                       headers={"User-Agent": "SmartTeacher/1.0"})
                pages = url_res.json().get("query", {}).get("pages", {})
                for p in pages.values():
                    info = p.get("imageinfo", [])
                    if info:
                        img_url = info[0].get("thumburl") or info[0].get("url", "")
                        if img_url and not is_bad_image(img_url):
                            print(f"[DEBUG] Wikimedia map: {img_url}")
                            return img_url
    except Exception as e:
        print(f"[DEBUG] Wikimedia map error: {e}")
    return None

def get_wikipedia_image(query, is_map=False):
    """מחזיר תמונה מ-Wikipedia"""
    try:
        api_url = "https://en.wikipedia.org/w/api.php"
        search_params = {
            "action": "query",
            "list": "search",
            "srsearch": query,
            "srlimit": 5,
            "format": "json"
        }
        results = requests.get(api_url, params=search_params, timeout=6,
                               headers={"User-Agent": "SmartTeacher/1.0"}).json()
        results = results.get("query", {}).get("search", [])

        for result in results[:3]:
            page_title = result["title"]
            # קבל את כל התמונות בדף
            img_params = {
                "action": "query",
                "titles": page_title,
                "prop": "images",
                "imlimit": 30,
                "format": "json"
            }
            img_res = requests.get(api_url, params=img_params, timeout=6,
                                   headers={"User-Agent": "SmartTeacher/1.0"}).json()
            pages = img_res.get("query", {}).get("pages", {})

            candidates = []
            for page in pages.values():
                for img in page.get("images", []):
                    t = img.get("title", "")
                    t_lower = t.lower()
                    if not any(ext in t_lower for ext in [".jpg", ".jpeg", ".png"]):
                        continue
                    if is_bad_image(t):
                        continue
                    if is_map and any(k in t_lower for k in ["map", "topograph", "relief", "terrain"]):
                        candidates.insert(0, t)  # עדיפות למפות
                    else:
                        candidates.append(t)

            for img_title in candidates[:5]:
                url_params = {
                    "action": "query",
                    "titles": img_title,
                    "prop": "imageinfo",
                    "iiprop": "url",
                    "iiurlwidth": 1000,
                    "format": "json"
                }
                url_pages = requests.get(api_url, params=url_params, timeout=6,
                                         headers={"User-Agent": "SmartTeacher/1.0"}).json()
                url_pages = url_pages.get("query", {}).get("pages", {})
                for p in url_pages.values():
                    info = p.get("imageinfo", [])
                    if info:
                        img_url = info[0].get("thumburl") or info[0].get("url", "")
                        if img_url and not is_bad_image(img_url):
                            print(f"[DEBUG] Wikipedia image: {img_url}")
                            return img_url
    except Exception as e:
        print(f"[DEBUG] Wikipedia error: {e}")
    return None

def build_image_url(user_input):
    is_map = any(word in user_input for word in MAP_WORDS)
    english_query = translate_to_english(user_input)
    print(f"[DEBUG] query='{english_query}' is_map={is_map}")

    if is_map:
        # נסה קודם Wikimedia Commons מפות
        img_url = search_wikimedia_map(english_query)
        if img_url:
            return img_url

    # נסה Wikipedia
    img_url = get_wikipedia_image(english_query, is_map=is_map)
    if img_url:
        return img_url

    # גיבוי Picsum
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
המשתמש ביקש תמונה/מפה — המערכת כבר מציגה אותה אוטומטית.
תפקידך: ספק תיאור אקדמי מפורט של הנושא בלבד. אל תזכיר שאינך יכול להציג תמונות.
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