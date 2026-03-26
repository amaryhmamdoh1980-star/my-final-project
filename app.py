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

MAP_WORDS   = ["מפה", "מפת", "خريطة", "خريطه"]
IMAGE_WORDS = ["צייר", "תמונה", "תראה לי", "תצלום", "איור",
               "صورة", "صوره", "أرني", "ارسم", "رسم", "صور", "اعرض"]
VIDEO_WORDS = [
    # עברית
    "סרטון", "וידאו", "סרט", "הראה לי סרטון", "תראה לי סרטון",
    "תן לי סרטון", "תראה לי וידאו", "רוצה לראות", "תן לי וידאו",
    # ערבית
    "فيديو", "مقطع فيديو", "مقطع", "فلم", "شاهد",
    "أرني فيديو", "أرني مقطع", "اعرض لي فيديو", "اعرض فيديو",
    "أريد مشاهدة", "بث", "تشغيل",
]

def detect_lang(text):
    if re.search(r'[\u0600-\u06FF]', text):
        return 'ar'
    if re.search(r'[\u0590-\u05FF]', text):
        return 'he'
    return 'en'

HE_TO_EN = {
    "תראה לי את": "", "תראה לי": "",
    "צייר לי": "", "צייר": "",
    "תמונה של": "", "תמונה": "",
    "מפה של": "", "מפת": "", "מפה": "",
    "תצלום של": "", "תצלום": "",
    "איור של": "", "איור": "",
    "סרטון על": "", "סרטון של": "", "סרטון": "",
    "וידאו על": "", "וידאו של": "", "וידאו": "",
    "סרט על": "", "סרט": "",
    "הראה לי סרטון על": "", "תראה לי סרטון על": "",
    "תן לי סרטון על": "", "רוצה לראות": "",
    "של": "", "את": "", "לי": "", "אז": "", "על": "",
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
    "קריסטל": "crystal quartz", "קוורץ": "quartz mineral",
    "זהב": "gold mineral", "כסף": "silver mineral", "נחושת": "copper mineral",
    "ריוליט": "rhyolite rock", "אנדזיט": "andesite rock",
    "גברו": "gabbro rock", "דיאבז": "diabase rock",
    "פרידוטיט": "peridotite rock", "טוף": "tuff volcanic rock",
    "פומיס": "pumice rock", "אובסידיאן": "obsidian volcanic glass",
    "בזלת עמודי": "columnar basalt", "לבה": "lava rock",
    "אבן חול": "sandstone rock", "אבן חולית": "sandstone",
    "צור": "flint rock", "חלמיש": "flint",
    "שיסט חרסיתי": "shale rock", "חרסית": "clay mineral",
    "גיר אלמוגים": "coral limestone", "קונגלומרט": "conglomerate rock",
    "ברקציה": "breccia rock", "חוואר": "marl rock",
    "גנייס": "gneiss rock", "שיסט": "schist rock",
    "קוורציט": "quartzite rock", "פילייט": "phyllite rock",
    "הורנפלס": "hornfels rock", "מיגמטיט": "migmatite rock",
    "פיריט": "pyrite mineral fool's gold",
    "קלציט": "calcite mineral", "פלדספר": "feldspar mineral",
    "מיקה": "mica mineral", "מוסקוביט": "muscovite mica",
    "ביוטיט": "biotite mica", "גבס": "gypsum mineral",
    "הליט": "halite rock salt mineral",
    "מגנטיט": "magnetite mineral", "המטיט": "hematite mineral",
    "לימוניט": "limonite mineral", "גתיט": "goethite mineral",
    "מלכיט": "malachite mineral", "אזוריט": "azurite mineral",
    "גלנה": "galena mineral", "ספלריט": "sphalerite mineral",
    "כלקופיריט": "chalcopyrite mineral",
    "אוליבין": "olivine mineral", "פירוקסן": "pyroxene mineral",
    "אמפיבול": "amphibole mineral", "הורנבלנד": "hornblende mineral",
    "גרנט": "garnet mineral", "אפידוט": "epidote mineral",
    "טלק": "talc mineral", "כלוריט": "chlorite mineral",
    "זרקון": "zircon mineral", "אפטיט": "apatite mineral",
    "טורמלין": "tourmaline mineral", "פלואוריט": "fluorite mineral",
    "יהלום": "diamond gemstone", "אודם": "ruby gemstone",
    "ספיר": "sapphire gemstone", "אמרלד": "emerald gemstone",
    "אמתיסט": "amethyst gemstone", "טופז": "topaz gemstone",
    "אוניקס": "onyx gemstone", "אופל": "opal gemstone",
    "ירקן": "jade gemstone", "פנינה": "pearl",
    "לפיס לזולי": "lapis lazuli gemstone",
    "פחם": "coal", "זרחן": "phosphorite rock", "גופרית": "sulfur mineral",
    "שמש": "sun", "ירח": "moon", "אש": "fire",
    "דינוזאור": "dinosaur", "פיל": "elephant",
    "אריה": "lion", "נשר": "eagle", "כריש": "shark",
    "עץ": "tree", "פרח": "flower", "ורד": "rose",
    "צרפת": "France", "גרמניה": "Germany", "ספרד": "Spain",
    "איטליה": "Italy", "יוון": "Greece", "מצרים": "Egypt",
    "ירדן": "Jordan", "סוריה": "Syria", "לבנון": "Lebanon",
    "ארצות הברית": "United States", "אמריקה": "United States",
    "רוסיה": "Russia", "סין": "China", "יפן": "Japan",
    "הודו": "India", "ברזיל": "Brazil", "אוסטרליה": "Australia",
    "קנדה": "Canada", "בריטניה": "United Kingdom", "טורקיה": "Turkey",
}

AR_TO_EN = {
    "أرني": "", "ارسم لي": "", "ارسم": "",
    "صورة من": "", "صورة لـ": "", "صورة": "", "صوره": "",
    "رسم": "", "رسمة": "", "اعرض لي": "", "اعرض": "",
    "أريد مشاهدة": "", "أرني فيديو عن": "", "أرني مقطع عن": "",
    "فيديو عن": "", "فيديو": "", "مقطع فيديو عن": "", "مقطع فيديو": "",
    "مقطع عن": "", "مقطع": "", "فلم عن": "", "فلم": "",
    "شاهد": "", "بث": "", "تشغيل": "",
    "خريطة": "map", "خريطه": "map",
    "إسرائيل": "Israel", "فلسطين": "Palestine",
    "القدس": "Jerusalem", "تل أبيب": "Tel Aviv",
    "حيفا": "Haifa", "إيلات": "Eilat",
    "النقب": "Negev", "الجليل": "Galilee",
    "البحر الميت": "Dead Sea", "بحيرة طبريا": "Sea of Galilee",
    "البحر المتوسط": "Mediterranean Sea", "البحر الأحمر": "Red Sea",
    "جبل": "mountain", "صحراء": "desert",
    "غابة": "forest", "شاطئ": "beach",
    "نهر": "river", "بحيرة": "lake",
    "بازلت": "basalt rock", "بازالت": "basalt rock",
    "جرانيت": "granite rock", "ريوليت": "rhyolite rock",
    "أنديزيت": "andesite rock", "غابرو": "gabbro rock",
    "بيريدوتيت": "peridotite rock",
    "توف بركاني": "tuff volcanic rock", "توف": "tuff rock",
    "بيوميس": "pumice rock", "خفاف": "pumice rock",
    "أوبسيديان": "obsidian volcanic glass", "زجاج بركاني": "obsidian",
    "حمم": "lava rock", "لافا": "lava",
    "بازلت عمودي": "columnar basalt",
    "رخام": "marble rock", "مرمر": "marble rock",
    "حجر جيري": "limestone rock", "كلس": "limestone",
    "دولوميت": "dolomite rock", "حجر رملي": "sandstone rock",
    "صوان": "flint rock", "طفلة": "shale rock",
    "طين": "clay mineral", "مارل": "marl rock",
    "كونغلوميرات": "conglomerate rock", "بريشيا": "breccia rock",
    "فحم": "coal",
    "نيس": "gneiss rock", "شيست": "schist rock",
    "كوارتزيت": "quartzite rock", "فيليت": "phyllite rock",
    "هورنفلس": "hornfels rock",
    "كوارتز": "quartz mineral", "معدن": "mineral",
    "صخرة": "rock", "حجر": "stone",
    "بيريت": "pyrite mineral", "كالسيت": "calcite mineral",
    "فيلدسبار": "feldspar mineral", "ميكا": "mica mineral",
    "جبس": "gypsum mineral", "ملح صخري": "halite rock salt",
    "مغنتيت": "magnetite mineral", "هيماتيت": "hematite mineral",
    "مالاكيت": "malachite mineral", "أزوريت": "azurite mineral",
    "غالينا": "galena mineral", "كالكوبيريت": "chalcopyrite mineral",
    "أوليفين": "olivine mineral", "بيروكسين": "pyroxene mineral",
    "أمفيبول": "amphibole mineral", "غارنيت": "garnet mineral",
    "تالك": "talc mineral", "فلوريت": "fluorite mineral",
    "توربالين": "tourmaline mineral", "زيركون": "zircon mineral",
    "ماسة": "diamond gemstone", "الماسة": "diamond",
    "ياقوت": "ruby gemstone", "زمرد": "emerald gemstone",
    "أميثيست": "amethyst gemstone", "توباز": "topaz gemstone",
    "عقيق": "agate gemstone", "لؤلؤ": "pearl",
    "لازورد": "lapis lazuli gemstone",
    "ذهب": "gold mineral", "فضة": "silver mineral",
    "نحاس": "copper mineral", "حديد": "iron mineral",
    "شمس": "sun", "قمر": "moon", "نار": "fire",
    "بركان": "volcano", "ديناصور": "dinosaur",
    "فيل": "elephant", "أسد": "lion",
    "شجرة": "tree", "وردة": "rose",
    "مصر": "Egypt", "الأردن": "Jordan", "سوريا": "Syria",
    "لبنان": "Lebanon", "السعودية": "Saudi Arabia",
    "فرنسا": "France", "ألمانيا": "Germany", "إسبانيا": "Spain",
    "إيطاليا": "Italy", "اليونان": "Greece",
    "الولايات المتحدة": "United States", "أمريكا": "United States",
    "روسيا": "Russia", "الصين": "China", "اليابان": "Japan",
    "الهند": "India", "البرازيل": "Brazil", "أستراليا": "Australia",
    "من": "", "في": "", "على": "", "إلى": "", "عن": "",
    "هو": "", "هي": "", "هذا": "", "هذه": "",
    "ما": "", "ماذا": "", "كيف": "", "لماذا": "",
    "لي": "", "لك": "", "أو": "", "مع": "", "بين": "",
    "نوع": "", "أنواع": "", "شكل": "",
}

BAD_KEYWORDS = ["globe", "locator", "orthographic", "Flag_of", "Coat_of",
                 "emblem", "seal", "banner", "logo", "icon", "portrait",
                 "newspaper", "magazine", "article", "stamp"]

# ─────────────────── File extraction ───────────────────
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

# ─────────────────── Translation ───────────────────
def translate_to_english(text):
    result = text
    is_arabic = bool(re.search(r'[\u0600-\u06FF]', text))
    is_hebrew = bool(re.search(r'[\u0590-\u05FF]', text))

    if is_arabic:
        for ar, eng in sorted(AR_TO_EN.items(), key=lambda x: -len(x[0])):
            result = result.replace(ar, f" {eng} " if eng else " ")
        result = re.sub(r'\s+', ' ', result).strip()
        if re.search(r'[\u0600-\u06FF]', result):
            result = re.sub(r'[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]+', '', result)
            result = re.sub(r'\s+', ' ', result).strip()
    elif is_hebrew:
        for heb, eng in sorted(HE_TO_EN.items(), key=lambda x: -len(x[0])):
            result = result.replace(heb, f" {eng} " if eng else " ")
        result = re.sub(r'\s+', ' ', result).strip()
        if re.search(r'[\u0590-\u05FF]', result):
            result = re.sub(r'[\u0590-\u05FF]+', '', result)
            result = re.sub(r'\s+', ' ', result).strip()

    return result.strip() or "nature"

def is_bad_image(url):
    return any(bad.lower() in url.lower() for bad in BAD_KEYWORDS)

# ─────────────────── YouTube video search ───────────────────
def get_youtube_video(query, lang='he'):
    """Search YouTube Data API v3. Returns embed URL or None."""
    if not API_KEY:
        return None
    try:
        # First try: search in user's language
        if lang == 'he':
            lang_query = f"{query} בעברית"
            relevance_lang = 'he'
        elif lang == 'ar':
            lang_query = f"{query} بالعربية"
            relevance_lang = 'ar'
        else:
            lang_query = query
            relevance_lang = 'en'

        params = {
            "part": "snippet",
            "q": lang_query,
            "type": "video",
            "maxResults": 5,
            "relevanceLanguage": relevance_lang,
            "safeSearch": "strict",
            "videoEmbeddable": "true",
            "key": API_KEY,
        }
        resp = requests.get(
            "https://www.googleapis.com/youtube/v3/search",
            params=params, timeout=8
        ).json()

        for item in resp.get("items", []):
            video_id = item.get("id", {}).get("videoId")
            if video_id:
                return f"https://www.youtube.com/embed/{video_id}?rel=0&modestbranding=1"

        # Fallback: English query
        if lang != 'en':
            params["q"] = query
            params["relevanceLanguage"] = "en"
            resp2 = requests.get(
                "https://www.googleapis.com/youtube/v3/search",
                params=params, timeout=8
            ).json()
            for item in resp2.get("items", []):
                video_id = item.get("id", {}).get("videoId")
                if video_id:
                    return f"https://www.youtube.com/embed/{video_id}?rel=0&modestbranding=1"

    except Exception as e:
        print(f"[DEBUG] YouTube API error: {e}")
    return None

# ─────────────────── Wikipedia image search ───────────────────
def get_wikipedia_image(query, is_map=False):
    try:
        api_url = "https://en.wikipedia.org/w/api.php"

        resp = requests.get(api_url, params={
            "action": "query",
            "generator": "search",
            "gsrsearch": query,
            "gsrlimit": 5,
            "prop": "pageimages",
            "pithumbsize": 1200,
            "pilimit": 5,
            "format": "json"
        }, timeout=8, headers={"User-Agent": "SmartTeacher/1.0"}).json()

        pages = resp.get("query", {}).get("pages", {})
        sorted_pages = sorted(pages.values(), key=lambda x: x.get('index', 999))
        for page in sorted_pages:
            thumbnail = page.get("thumbnail", {})
            if thumbnail and thumbnail.get("source"):
                img_url = thumbnail["source"]
                if not is_bad_image(img_url):
                    img_url = re.sub(r'/\d+px-', '/1200px-', img_url)
                    return img_url

        search_resp = requests.get(api_url, params={
            "action": "query", "list": "search",
            "srsearch": query, "srlimit": 3, "format": "json"
        }, timeout=6, headers={"User-Agent": "SmartTeacher/1.0"}).json()

        for result in search_resp.get("query", {}).get("search", [])[:2]:
            page_title = result["title"]
            pi_resp = requests.get(api_url, params={
                "action": "query", "titles": page_title,
                "prop": "pageimages", "pithumbsize": 1200, "format": "json"
            }, timeout=6, headers={"User-Agent": "SmartTeacher/1.0"}).json()
            for page in pi_resp.get("query", {}).get("pages", {}).values():
                thumbnail = page.get("thumbnail", {})
                if thumbnail and thumbnail.get("source"):
                    img_url = thumbnail["source"]
                    if not is_bad_image(img_url):
                        img_url = re.sub(r'/\d+px-', '/1200px-', img_url)
                        return img_url

    except Exception as e:
        print(f"[DEBUG] Wikipedia pageimages error: {e}")

    try:
        commons_url = "https://commons.wikimedia.org/w/api.php"
        commons_resp = requests.get(commons_url, params={
            "action": "query",
            "generator": "search",
            "gsrsearch": query,
            "gsrnamespace": 6,
            "gsrlimit": 5,
            "prop": "imageinfo",
            "iiprop": "url",
            "iiurlwidth": 1200,
            "format": "json"
        }, timeout=6, headers={"User-Agent": "SmartTeacher/1.0"}).json()

        for page in commons_resp.get("query", {}).get("pages", {}).values():
            info = page.get("imageinfo", [])
            if info:
                img_url = info[0].get("thumburl") or info[0].get("url", "")
                if img_url and not is_bad_image(img_url):
                    return img_url

    except Exception as e:
        print(f"[DEBUG] Commons error: {e}")

    return None

def build_image_url(user_input):
    is_map = any(word in user_input for word in MAP_WORDS)
    english_query = translate_to_english(user_input)
    if is_map:
        english_query += " map geography"
    print(f"[DEBUG] Translated image query: '{english_query}'")
    img_url = get_wikipedia_image(english_query, is_map=is_map)
    if img_url:
        return img_url
    seed = int(hashlib.md5(english_query.encode()).hexdigest()[:8], 16) % 1000
    return f"https://picsum.photos/seed/{seed}/1024/768"

def build_video_url(user_input):
    lang = detect_lang(user_input)
    english_query = translate_to_english(user_input)
    print(f"[DEBUG] Translated video query: '{english_query}' lang={lang}")
    return get_youtube_video(english_query, lang=lang)

# ─────────────────── System prompt ───────────────────
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

# ─────────────────── Routes ───────────────────
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

    # Priority: video > image/map  (mutually exclusive per request)
    wants_video = (
        not has_uploaded_file and
        any(word in user_input for word in VIDEO_WORDS)
    )
    wants_visual = (
        not has_uploaded_file and
        not wants_video and
        any(word in user_input for word in MAP_WORDS + IMAGE_WORDS)
    )

    image_url = build_image_url(user_input) if wants_visual else None
    video_url = build_video_url(user_input) if wants_video else None

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
    elif wants_video:
        prompt_text = f"""{SYSTEM_PROMPT}

המשתמש ביקש סרטון — המערכת מציגה אותו אוטומטית.
תפקידך: תאר את הנושא בקצרה (2-3 משפטים) כמבוא לסרטון. אל תזכיר שאינך יכול להציג סרטונים.

שאלה: {user_input}"""
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
        return jsonify({"reply": reply, "image_url": image_url, "video_url": video_url})
    except Exception as e:
        return jsonify({"reply": f"תקלה: {str(e)}", "image_url": image_url, "video_url": video_url})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)