import os
import requests
import base64
import json
import re
import hashlib
import io
from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text

app = Flask(__name__)

DB_URL = os.environ.get('DATABASE_URL', 'postgresql://postgres.yimsexytrswzamnslgcd:MaAm%40036355972@aws-0-ap-northeast-1.pooler.supabase.com:6543/postgres')
app.config['SQLALCHEMY_DATABASE_URI'] = DB_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAX_CONTENT_LENGTH'] = 20 * 1024 * 1024
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
}

BAD_KEYWORDS = ["globe", "locator", "orthographic", "Flag_of", "Coat_of",
                 "emblem", "seal", "banner", "logo", "icon", "portrait",
                 "newspaper", "magazine", "article", "stamp"]

def extract_text_from_pdf(file_bytes):
    try:
        import fitz
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        return "".join(page.get_text() for page in doc)[:8000]
    except Exception as e:
        return f"[שגיאה בקריאת PDF: {e}]"

def extract_text_from_docx(file_bytes):
    try:
        from docx import Document
        doc = Document(io.BytesIO(file_bytes))
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())[:8000]
    except Exception as e:
        return f"[שגיאה בקריאת Word: {e}]"

def extract_text_from_xlsx(file_bytes):
    try:
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
        text = ""
        for sheet in wb.sheetnames:
            ws = wb[sheet]
            text += f"\n--- גיליון: {sheet} ---\n"
            for row in ws.iter_rows(values_only=True):
                row_text = " | ".join(str(c) for c in row if c is not None)
                if row_text.strip():
                    text += row_text + "\n"
        return text[:8000]
    except Exception as e:
        return f"[שגיאה בקריאת Excel: {e}]"

def extract_text_from_file(file_bytes, filename, mimetype):
    fname = filename.lower()
    if fname.endswith(".pdf") or "pdf" in mimetype:
        return extract_text_from_pdf(file_bytes), "PDF"
    elif fname.endswith(".docx") or "word" in mimetype:
        return extract_text_from_docx(file_bytes), "Word"
    elif fname.endswith(".xlsx") or "excel" in mimetype or "spreadsheet" in mimetype:
        return extract_text_from_xlsx(file_bytes), "Excel"
    elif fname.endswith(".txt") or "text/plain" in mimetype:
        return file_bytes.decode("utf-8", errors="ignore")[:8000], "טקסט"
    return None, None

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

def get_wikipedia_image(query, is_map=False):
    try:
        api_url = "https://en.wikipedia.org/w/api.php"
        results = requests.get(api_url, params={
            "action": "query", "list": "search",
            "srsearch": query, "srlimit": 5, "format": "json"
        }, timeout=6, headers={"User-Agent": "SmartTeacher/1.0"}).json()
        results = results.get("query", {}).get("search", [])

        for result in results[:3]:
            page_title = result["title"]
            img_res = requests.get(api_url, params={
                "action": "query", "titles": page_title,
                "prop": "images", "imlimit": 30, "format": "json"
            }, timeout=6, headers={"User-Agent": "SmartTeacher/1.0"}).json()
            pages = img_res.get("query", {}).get("pages", {})
            candidates = []
            for page in pages.values():
                for img in page.get("images", []):
                    t = img.get("title", "")
                    if not any(ext in t.lower() for ext in [".jpg", ".jpeg", ".png"]):
                        continue
                    if is_bad_image(t):
                        continue
                    if is_map and any(k in t.lower() for k in ["map", "topograph", "relief", "terrain"]):
                        candidates.insert(0, t)
                    else:
                        candidates.append(t)

            for img_title in candidates[:5]:
                url_pages = requests.get(api_url, params={
                    "action": "query", "titles": img_title,
                    "prop": "imageinfo", "iiprop": "url",
                    "iiurlwidth": 1000, "format": "json"
                }, timeout=6, headers={"User-Agent": "SmartTeacher/1.0"}).json()
                for p in url_pages.get("query", {}).get("pages", {}).values():
                    info = p.get("imageinfo", [])
                    if info:
                        img_url = info[0].get("thumburl") or info[0].get("url", "")
                        if img_url and not is_bad_image(img_url):
                            return img_url
    except Exception as e:
        print(f"[DEBUG] Wikipedia error: {e}")
    return None

def build_image_url(user_input):
    is_map = any(word in user_input for word in MAP_WORDS)
    english_query = translate_to_english(user_input)
    if is_map:
        english_query += " map geography"
    img_url = get_wikipedia_image(english_query, is_map=is_map)
    if img_url:
        return img_url
    seed = int(hashlib.md5(english_query.encode()).hexdigest()[:8], 16) % 1000
    return f"https://picsum.photos/seed/{seed}/1024/768"

SYSTEM_PROMPT = """אתה 'המורה החכם' — מורה ומדען מנוסה ומומחה.

חוק מוחלט — פתיחת תשובה:
- NEVER start with: "כפרופסור", "בתור מומחה", "אציג", "אתחיל", "ברצוני", "אשמח להציג"
- התחל תמיד ישירות עם תוכן התשובה בהתאם לשאלה:
  * "מה רואים?" → "בתמונה רואים..."
  * "מה זה X?" → "X הוא..."
  * "למה?" → "הסיבה..."
  * "איך?" → "כדי ל..." / "התהליך..."
  * שאלה קצרה בשיחה ממושכת → תשובה ישירה ללא מבוא כלל
- ברמה אקדמית מתאימה לשאלה, בצורה מנומסת וברורה."""

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    user_input = request.form.get("message", "")
    image_file = request.files.get("image")
    doc_file   = request.files.get("document")
    history_raw = request.form.get("history", "[]")

    try:
        history = json.loads(history_raw)
    except:
        history = []

    if not user_input and not image_file and not doc_file:
        return jsonify({"reply": "Empty message"}), 400

    doc_text, doc_type = None, None
    if doc_file and doc_file.filename:
        file_bytes = doc_file.read()
        doc_text, doc_type = extract_text_from_file(
            file_bytes, doc_file.filename, doc_file.content_type or ""
        )

    has_uploaded_file = (image_file and image_file.filename) or (doc_file and doc_file.filename)

    wants_visual = (
        not has_uploaded_file and
        any(word in user_input for word in MAP_WORDS + IMAGE_WORDS)
    )
    image_url = build_image_url(user_input) if wants_visual else None

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={API_KEY}"
    headers = {'Content-Type': 'application/json'}

    if doc_text:
        user_question = user_input if user_input else "סכם את הקובץ בצורה מפורטת"
        prompt_text = f"""{SYSTEM_PROMPT}

המשתמש העלה קובץ {doc_type}. ענה על שאלתו על סמך תוכן הקובץ בלבד.

תוכן הקובץ:
---
{doc_text}
---

שאלה: {user_question}"""
    elif wants_visual:
        prompt_text = f"""{SYSTEM_PROMPT}

המשתמש ביקש תמונה/מפה — המערכת מציגה אותה אוטומטית.
תפקידך: תאר את הנושא בהתאם לשאלה. אל תזכיר שאינך יכול להציג תמונות.

שאלה: {user_input}"""
    else:
        prompt_text = f"""{SYSTEM_PROMPT}

שאלה: {user_input}"""

    contents = []
    for msg in history:
        role = "user" if msg['role'] == "user" else "model"
        contents.append({"role": role, "parts": [{"text": msg['text']}]})

    current_parts = [{"text": prompt_text}]
    if image_file and image_file.filename:
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
            reply = "שגיאת שרת גוגל."
            print(f"[DEBUG] Gemini error {response.status_code}")
        try:
            label = user_input or (doc_file.filename if doc_file else "תמונה")
            db.execute("INSERT INTO history (user_message, bot_message) VALUES (?, ?)", label, reply)
        except: pass
        return jsonify({"reply": reply, "image_url": image_url})
    except Exception as e:
        return jsonify({"reply": f"תקלה: {str(e)}", "image_url": image_url})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)