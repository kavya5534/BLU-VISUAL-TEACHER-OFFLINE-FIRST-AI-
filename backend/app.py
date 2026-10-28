import json, os, re, subprocess, uuid, time, hashlib
from pathlib import Path
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Header, Depends
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import requests
from .schema import Lesson, QuizQuestion, Flashcard
from .tts import synthesize, NEURAL_VOICES, FEMALE_VOICES, LANGUAGE_NAMES
from .exporter import make_mp4
from .auth import register_user, login_user, get_current_user, update_user_progress
from .control_center import (
    get_full_control_center_status,
    set_offline_mode,
    clear_cache_storage
)
from .ai_brain import (
    explain_topic,
    generate_flashcards,
    generate_practice_questions,
    summarize_notes,
    get_kannada_bilingual_explanation
)
from .ocr_tutor import (
    extract_text_from_pdf,
    analyze_textbook_image,
    convert_content_to_study_aids
)

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = ROOT / "generated"
AUDIO_DIR = OUT / "audio"
UPLOADS = OUT / "uploads"

OUT.mkdir(exist_ok=True)
AUDIO_DIR.mkdir(exist_ok=True)
UPLOADS.mkdir(exist_ok=True)

app = FastAPI(title="Blu Visual Teacher — AI Multilingual Platform", version="0.4.0")
app.mount("/static", StaticFiles(directory=ROOT / "frontend"), name="static")
app.mount("/media", StaticFiles(directory=OUT), name="media")

# Load sample lessons and course catalog
SAMPLES = json.loads((DATA / "sample_lessons.json").read_text(encoding="utf-8"))
COURSE_CATALOG_PATH = DATA / "course_library.json"

def get_course_catalog() -> list[dict]:
    courses = []
    if COURSE_CATALOG_PATH.exists():
        try:
            courses = json.loads(COURSE_CATALOG_PATH.read_text(encoding="utf-8"))
        except Exception:
            courses = []
    custom_courses_file = OUT / "custom_courses.json"
    if custom_courses_file.exists():
        try:
            custom_courses = json.loads(custom_courses_file.read_text(encoding="utf-8"))
            courses.extend(custom_courses)
        except Exception:
            pass
    return courses

# Multilingual Topic Template Engine
MULTILINGUAL_TEMPLATES = {
    "en": {
        "title": "Mastering: {topic}",
        "intro_heading": "What is {topic}?",
        "intro_narr": "{topic} is an essential concept designed for {level} learners. It provides a structured approach to solving problems and understanding modern systems.",
        "step_heading": "How {topic} Works Step-by-Step",
        "step_code": "# Understanding {topic}\ndef explore_{slug}():\n    concept = '{topic}'\n    status = 'active'\n    print(f'Applying: {{concept}}')\n    return True\n\nexplore_{slug}()",
        "step_narr": "To understand {topic}, we break it down into core logical steps. Each component executes in order to produce predictable, efficient results.",
        "diag_heading": "Visual Architecture of {topic}",
        "diag_items": ["Input / Initiation", "{topic} Processing", "Validation Check", "Output & Execution"],
        "diag_narr": "Here is the visual lifecycle: from the initial stimulus or data, through the core transformation of {topic}, to the verified outcome.",
        "quiz_q1": "What is the primary foundation of {topic}?",
        "quiz_o1": ["Structured execution and clear rules", "Random unmonitored behavior", "Turning off the machine", "Ignoring inputs"],
        "quiz_exp1": "{topic} relies on structured, well-defined rules to operate reliably.",
        "quiz_q2": "Why is active practice critical when mastering {topic}?",
        "quiz_o2": ["It tests memory retrieval and reinforces neural connections", "It causes computer lag", "It is unnecessary", "It disables tests"],
        "quiz_exp2": "Active recall and visual tracing significantly enhance long-term mastery of {topic}.",
        "fc_f1": "Core Definition: {topic}",
        "fc_b1": "A key principle in modern studies that transforms basic inputs into structured solutions.",
        "fc_tip1": "Focus on the relationship between causes and effects.",
        "fc_f2": "Practical Use Case",
        "fc_b2": "{topic} is widely utilized in industry and science to automate, optimize, and organize complex workflows."
    },
    "hi": {
        "title": "सीखें: {topic}",
        "intro_heading": "{topic} क्या है?",
        "intro_narr": "{topic} {level} स्तर के शिक्षार्थियों के लिए एक अत्यंत महत्वपूर्ण अवधारणा है। यह समस्याओं को वैज्ञानिक और व्यावहारिक रूप से सुलझाने में मदद करता है।",
        "step_heading": "{topic} चरण-दर-चरण कैसे काम करता है",
        "step_code": "# {topic} का अवलोकन\ndef seekho_{slug}():\n    topic = '{topic}'\n    print(f'सीख रहे हैं: {{topic}}')\n    return 'सफल'\n\nseekho_{slug}()",
        "step_narr": "{topic} को समझने के लिए हम इसे सरल चरणों में विभाजित करते हैं। प्रत्येक चरण क्रमबद्ध तरीके से निष्पादित होता है।",
        "diag_heading": "{topic} की कार्यप्रणाली",
        "diag_items": ["प्रारंभिक इनपुट", "{topic} विश्लेषण", "सत्यापन जांच", "अंतिम परिणाम"],
        "diag_narr": "यह {topic} का चक्र है: इनपुट से शुरू होकर, मुख्य प्रक्रिया से गुजरते हुए, अंतिम और सटीक परिणाम तक पहुंचना।",
        "quiz_q1": "{topic} का मुख्य उद्देश्य क्या है?",
        "quiz_o1": ["प्रक्रिया को क्रमबद्ध और प्रभावी बनाना", "कंप्यूटर को धीमा करना", "कोड को मिटाना", "बिना सोचे समझे काम करना"],
        "quiz_exp1": "{topic} कार्यों को सटीक, सुव्यवस्थित और प्रभावी ढंग से निष्पादित करने में मदद करता है।",
        "quiz_q2": "{topic} का अध्ययन करते समय सबसे प्रभावी तरीका कौन सा है?",
        "quiz_o2": ["सक्रिय परीक्षण और विजुअल डायग्राम देखना", "केवल शीर्षकों को देखना", "अभ्यास न करना", "रैंडम अनुमान लगाना"],
        "quiz_exp2": "सक्रिय अभ्यास और दृश्य रेखाचित्रों के माध्यम से याद रखने की क्षमता कई गुना बढ़ जाती है।",
        "fc_f1": "{topic} की मूल परिभाषा",
        "fc_b1": "एक बुनियादी सिद्धांत जो जटिल समस्याओं को समझने योग्य और प्रभावी समाधानों में बदलता है।",
        "fc_tip1": "चरणों के आपसी संबंध पर ध्यान केंद्रित करें।",
        "fc_f2": "दैनिक जीवन में अनुप्रयोग",
        "fc_b2": "{topic} का उपयोग विज्ञान और प्रौद्योगिकी में प्रक्रियाओं को अनुकूलित करने के लिए किया जाता है।"
    },
    "ta": {
        "title": "கற்போம்: {topic}",
        "intro_heading": "{topic} என்றால் என்ன?",
        "intro_narr": "{topic} என்பது {level} நிலை மாணவர்களுக்கான அடிப்படை மற்றும் முக்கியமான பாடமாகும். இது சிக்கலான கருத்துக்களை எளிமையாகப் புரிந்துகொள்ள உதவுகிறது.",
        "step_heading": "{topic} எவ்வாறு இயங்குகிறது?",
        "step_code": "# {topic} விளக்கம்\ndef learn_{slug}():\n    concept = '{topic}'\n    print(f'கற்போம்: {{concept}}')\n    return True\n\nlearn_{slug}()",
        "step_narr": "{topic}-ஐப் புரிந்துகொள்ள அதன் அடிப்படை படிகளைப் பின்பற்ற வேண்டும். ஒவ்வொரு படிநிலையும் சரியான விளைவை ஏற்படுத்துகிறது.",
        "diag_heading": "{topic}-இன் காட்சி வரைபடம்",
        "diag_items": ["தொடக்க உள்ளீடு", "{topic} செயல்முறை", "சரிபார்ப்பு", "இறுதி வெளியீடு"],
        "diag_narr": "தொடக்க உள்ளீட்டில் தொடங்கி {topic}-இன் முக்கிய செயல்பாடு வழியே இறுதி முடிவை அடையும் சுழற்சி இதுவாகும்.",
        "quiz_q1": "{topic}-இன் முக்கிய நோக்கம் என்ன?",
        "quiz_o1": ["முறையான மற்றும் பயனுள்ள செயல்பாடு", "சீரற்ற வேலை", "கணினியை முடக்குதல்", "பயிற்சியைத் தவிர்த்தல்"],
        "quiz_exp1": "{topic} தெளிவான விதிமுறைகளுடன் துல்லியமாக செயல்பட உதவுகிறது.",
        "quiz_q2": "{topic}-ஐ ஆழமாகக் கற்க சிறந்த வழி எது?",
        "quiz_o2": ["காட்சிப் படங்கள் மற்றும் வினாடி வினாக்கள்", "மேலோட்டமாகப் பார்ப்பது மட்டும்", "பயிற்சியே செய்யாமல் இருப்பது", "யூகிப்பது"],
        "quiz_exp2": "காட்சிப் படங்கள் மூலம் கருத்துக்களை எளிதில் நினைவில் வைத்திருக்க முடியும்.",
        "fc_f1": "{topic} - முக்கிய கருத்து",
        "fc_b1": "சிக்கல்களைத் தீர்த்து தெளிவான விளைவை உருவாக்கும் முதன்மையான கோட்பாடு.",
        "fc_tip1": "காரணம் மற்றும் விளைவைக் கவனியுங்கள்.",
        "fc_f2": "பயன்பாடு",
        "fc_b2": "{topic} தொழில்நுட்பம் மற்றும் அறிவியலில் பரவலாகப் பயன்படுகிறது."
    },
    "te": {
        "title": "నేర్చుకుందాం: {topic}",
        "intro_heading": "{topic} అంటే ఏమిటి?",
        "intro_narr": "{topic} అనేది {level} అభ్యాసకుల కోసం రూపొందించబడిన ముఖ్యమైన భావన. ఇది సమస్యలను సులభంగా అర్థం చేసుకోవడానికి సహాయపడుతుంది.",
        "step_heading": "{topic} దశలవారీగా ఎలా పనిచేస్తుంది",
        "step_code": "# {topic} పరిశీలన\ndef learn_{slug}():\n    concept = '{topic}'\n    print(f'నేర్చుకుంటున్నాం: {{concept}}')\n    return True\n\nlearn_{slug}()",
        "step_narr": "{topic} ను విశ్లేషించి దశలవారీగా అర్థం చేసుకోవడం ద్వారా మనం సరైన ఫలితాలను సాధించవచ్చు.",
        "diag_heading": "{topic} నిర్మాణం",
        "diag_items": ["ఇన్‌పుట్ ప్రారంభం", "{topic} విశ్లేషణ", "ధృవీకరణ", "ఫలితం"],
        "diag_narr": "ఇన్‌పుట్ నుండి మొదలై {topic} ప్రక్రియ ద్వారా స్పష్టమైన ఫలితం చేరడం దీని పని విధానం.",
        "quiz_q1": "{topic} యొక్క ముఖ్య ప్రయోజనం ఏమిటి?",
        "quiz_o1": ["నిర్మాణాత్మక మరియు సమర్థవంతమైన నిర్వహణ", "యాదృచ్ఛిక చర్యలు", "కంప్యూటర్ స్లో చేయడం", "ఏమీ చేయకపోవడం"],
        "quiz_exp1": "{topic} సూత్రప్రాయంగా పనిచేస్తూ పనులను సులభతరం చేస్తుంది.",
        "quiz_q2": "{topic} ను దృఢంగా గుర్తుంచుకోవడానికి ఏమి చేయాలి?",
        "quiz_o2": ["క్విజ్‌లు మరియు ఫ్లాష్‌కార్డ్‌లతో సాధన", "కేవలం చదివి వదిలేయడం", "అభ్యాసం ఆపడం", "ఊహించడం"],
        "quiz_exp2": "యాక్టివ్ రీకాల్ మరియు విజువల్ చార్ట్‌లు అవగాహనను పెంచుతాయి.",
        "fc_f1": "{topic} ప్రాథమిక నిర్వచనం",
        "fc_b1": "సమస్యలను పరిష్కరించడానికి ఉపయోగపడే ఆధునిక సూత్రం.",
        "fc_tip1": "విధానాల మధ్య సంబంధాలను గమనించండి.",
        "fc_f2": "వాస్తవిక వినియోగం",
        "fc_b2": "{topic} వివిధ సాంకేతిక మరియు శాస్త్రీయ రంగాలలో ఉపయోగించబడుతుంది."
    },
    "kn": {
        "title": "ಕಲಿಯೋಣ: {topic}",
        "intro_heading": "{topic} ಎಂದರೇನು?",
        "intro_narr": "{topic} ಎಂಬುದು {level} ಕಲಿಯುವವರಿಗೆ ಅತ್ಯಂತ ಪ್ರಮುಖವಾದ ಪರಿಕಲ್ಪನೆಯಾಗಿದೆ. ಇದು ಜಟಿಲ ಸಮಸ್ಯೆಗಳನ್ನು ಸುಲಭವಾಗಿ ಅರ್ಥಮಾಡಿಕೊಳ್ಳಲು ನೆರವಾಗುತ್ತದೆ.",
        "step_heading": "{topic} ಹಂತ ಹಂತವಾಗಿ ಹೇಗೆ ಕೆಲಸ ಮಾಡುತ್ತದೆ",
        "step_code": "# {topic} ಅಧ್ಯಯನ\ndef learn_{slug}():\n    concept = '{topic}'\n    print(f'ಕಲಿಯುತ್ತಿದ್ದೇವೆ: {{concept}}')\n    return True\n\nlearn_{slug}()",
        "step_narr": "{topic} ಅನ್ನು ಅರ್ಥಮಾಡಿಕೊಳ್ಳಲು ಅದರ ಮೂಲ ತತ್ವಗಳನ್ನು ಅನುಸರಿಸಿ ಹಂತ ಹಂತವಾಗಿ ಸಾಗಬೇಕು.",
        "diag_heading": "{topic} ನ ರಚನೆ",
        "diag_items": ["ಆರಂಭಿಕ ಇನ್‌ಪುಟ್", "{topic} ಪ್ರಕ್ರಿಯೆ", "ಪರಿಶೀಲನೆ", "ಅಂತಿಮ ಫಲಿತಾಂಶ"],
        "diag_narr": "ಇನ್‌ಪುಟ್‌ನಿಂದ ಆರಂಭಿಸಿ {topic} ನ ಹಂತಗಳ ಮೂಲಕ ಸಾಗಿ ನಿಖರ ಫಲಿತಾಂಶವನ್ನು ಪಡೆಯಬಹುದು.",
        "quiz_q1": "{topic} ನ ಪ್ರಮುಖ ಗುರಿ ಏನು?",
        "quiz_o1": ["ಕ್ರಮಬದ್ಧ ಮತ್ತು ನಿಖರ ಕಾರ್ಯನಿರ್ವಹಣೆ", "ಯಾದೃಚ್ಛಿಕವಾಗಿ ಕಾರ್ಯ ನಿರ್ವಹಿಸುವುದು", "ಕಂಪ್ಯೂಟರ್ ನಿಲ್ಲಿಸುವುದು", "ಅಭ್ಯಾಸ ಮಾಡದಿರುವುದು"],
        "quiz_exp1": "{topic} ನಿಖರ ನಿಯಮಗಳ ಮೂಲಕ ಕಾರ್ಯವನ್ನು ಸುಲಭಗೊಳಿಸುತ್ತದೆ.",
        "quiz_q2": "{topic} ಅನ್ನು ಚೆನ್ನಾಗಿ ಕಲಿಯಲು ಯಾವುದು ಉತ್ತಮ?",
        "quiz_o2": ["ಕ್ವಿಜ್ ಮತ್ತು ಫ್ಲ್ಯಾಶ್ ಕಾರ್ಡ್ ಮೂಲಕ ಅಭ್ಯಾಸ", "ಕೇವಲ ಮುಖಪುಟ ನೋಡುವುದು", "ಅಭ್ಯಾಸ ತ್ಯಜಿಸುವುದು", "ಊಹಿಸುವುದು"],
        "quiz_exp2": "ದೃಶ್ಯ ಪರಿಕಲ್ಪನೆಗಳ ಮೂಲಕ ಕಲಿಯುವುದು ಸ್ಮರಣಶಕ್ತಿಯನ್ನು ಹೆಚ್ಚಿಸುತ್ತದೆ.",
        "fc_f1": "{topic} ನ ಮೂಲ ಪರಿಕಲ್ಪನೆ",
        "fc_b1": "ಸಮಸ್ಯೆಗಳನ್ನು ಪರಿಹರಿಸಲು ಸಹಾಯ ಮಾಡುವ ಪ್ರಮುಖ ನಿಯಮ.",
        "fc_tip1": "ಕಾರ್ಯ ಮತ್ತು ಫಲಿತಾಂಶದ ನಡುವಿನ ಸಂಬಂಧವನ್ನು ಗಮನಿಸಿ.",
        "fc_f2": "ಪ್ರಾಯೋಗಿಕ ಬಳಕೆ",
        "fc_b2": "{topic} ಅನ್ನು ನೈಜ ಜಗತ್ತಿನ ತಂತ್ರಜ್ಞಾನದಲ್ಲಿ ವ್ಯಾಪಕವಾಗಿ ಬಳಸಲಾಗುತ್ತದೆ."
    },
    "es": {
        "title": "Aprender: {topic}",
        "intro_heading": "¿Qué es {topic}?",
        "intro_narr": "{topic} es un concepto fundamental para estudiantes de nivel {level}. Proporciona un marco claro para resolver problemas complejos y entender la tecnología moderna.",
        "step_heading": "Cómo funciona {topic} paso a paso",
        "step_code": "# Explorando {topic}\ndef aprender_{slug}():\n    concepto = '{topic}'\n    print(f'Estudiando: {{concepto}}')\n    return True\n\naprender_{slug}()",
        "step_narr": "Para dominar {topic}, dividimos el proceso en etapas lógicas y predecibles que garantizan un resultado óptimo.",
        "diag_heading": "Arquitectura visual de {topic}",
        "diag_items": ["Entrada inicial", "Procesamiento de {topic}", "Verificación", "Resultado final"],
        "diag_narr": "El flujo completo: desde los datos iniciales, a través de la transformación de {topic}, hasta el resultado verificado.",
        "quiz_q1": "¿Cuál es el propósito principal de {topic}?",
        "quiz_o1": ["Estructurar y optimizar el proceso", "Hacer que el sistema falle", "Borrar información", "Evitar el aprendizaje"],
        "quiz_exp1": "{topic} proporciona un marco fiable y estructurado para alcanzar soluciones eficientes.",
        "quiz_q2": "¿Cuál es la mejor manera de dominar {topic}?",
        "quiz_o2": ["Práctica activa con cuestionarios y tarjetas", "Leer sin comprender", "Ignorar explicaciones", "Adivinar respuestas"],
        "quiz_exp2": "La recuperación activa y los diagramas visuales consolidan el conocimiento a largo plazo.",
        "fc_f1": "Definición clave: {topic}",
        "fc_b1": "Un principio fundamental para transformar entradas en resultados estructurados y confiables.",
        "fc_tip1": "Observa la relación entre entrada y salida.",
        "fc_f2": "Aplicación práctica",
        "fc_b2": "{topic} se utiliza ampliamente en la industria y el desarrollo para automatizar procesos."
    }
}

def generate_topic_aware_lesson(topic: str, level: str, language: str) -> dict:
    tmpl = MULTILINGUAL_TEMPLATES.get(language, MULTILINGUAL_TEMPLATES["en"])
    slug = re.sub(r"[^a-zA-Z0-9_]", "_", topic).lower()[:20] or "concept"
    
    title = tmpl["title"].format(topic=topic)
    scenes = [
        {
            "type": "title_card",
            "heading": tmpl["intro_heading"].format(topic=topic),
            "narration": tmpl["intro_narr"].format(topic=topic, level=level)
        },
        {
            "type": "code_walkthrough",
            "heading": tmpl["step_heading"].format(topic=topic),
            "code": tmpl["step_code"].format(topic=topic, slug=slug),
            "highlight_lines": [1, 3],
            "narration": tmpl["step_narr"].format(topic=topic)
        },
        {
            "type": "diagram",
            "heading": tmpl["diag_heading"].format(topic=topic),
            "items": [item.format(topic=topic) for item in tmpl["diag_items"]],
            "narration": tmpl["diag_narr"].format(topic=topic)
        }
    ]

    quizzes = [
        {
            "id": 1,
            "question": tmpl["quiz_q1"].format(topic=topic),
            "options": tmpl["quiz_o1"],
            "answer": 0,
            "explanation": tmpl["quiz_exp1"].format(topic=topic)
        },
        {
            "id": 2,
            "question": tmpl["quiz_q2"].format(topic=topic),
            "options": tmpl["quiz_o2"],
            "answer": 0,
            "explanation": tmpl["quiz_exp2"].format(topic=topic)
        }
    ]

    flashcards = [
        {
            "front": tmpl["fc_f1"].format(topic=topic),
            "back": tmpl["fc_b1"].format(topic=topic),
            "tip": tmpl.get("fc_tip1", "Focus on core ideas.")
        },
        {
            "front": tmpl["fc_f2"].format(topic=topic),
            "back": tmpl["fc_b2"].format(topic=topic),
            "tip": "Think about real-world scenarios."
        }
    ]

    return {
        "title": title,
        "level": level,
        "language": language,
        "category": "Educational",
        "scenes": scenes,
        "quizzes": quizzes,
        "flashcards": flashcards,
        "summary": f"Comprehensive visual lesson on {topic} in {LANGUAGE_NAMES.get(language, language)}."
    }

def plan_with_ollama(topic: str, level: str, language: str, seconds: int) -> dict | None:
    model = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
    prompt = f"""Return valid JSON matching this schema:
{{
  "title": string,
  "level": "{level}",
  "language": "{language}",
  "category": string,
  "scenes": [
    {{"type": "title_card"|"diagram"|"code_walkthrough", "heading": string, "narration": string, "code"?: string, "highlight_lines"?: number[], "items"?: string[]}}
  ],
  "quizzes": [
    {{"question": string, "options": [string, string, string, string], "answer": number, "explanation": string}}
  ],
  "flashcards": [
    {{"front": string, "back": string, "tip": string}}
  ]
}}
Create 3-5 clear teaching scenes about {topic!r}. Use language code {language}.
Include 2-3 multiple-choice quiz questions and 2-3 flashcards about {topic!r}.
Aim for about {seconds} seconds total. Return JSON only with no markdown wrapping."""

    try:
        response = requests.post(
            "http://127.0.0.1:11434/api/generate",
            json={"model": model, "prompt": prompt, "stream": False, "format": "json"},
            timeout=90
        )
        response.raise_for_status()
        raw = response.json().get("response", "")
        parsed = json.loads(raw)
        return Lesson.model_validate(parsed).model_dump()
    except Exception:
        return None

# ==========================================================================
# 1. OFFLINE CONTROL CENTER ROUTES
# ==========================================================================
@app.get("/api/control-center/status")
def control_center_status():
    """Return independent status of Local AI, DB, Audio, Internet & Storage."""
    return get_full_control_center_status()

@app.post("/api/control-center/toggle-offline")
def toggle_offline(payload: dict):
    """Toggle 100% strict offline mode on/off."""
    enabled = bool(payload.get("enabled", False))
    new_state = set_offline_mode(enabled)
    return {
        "status": "success",
        "strict_offline_mode": new_state,
        "message": "Strict Offline Mode Activated (External network requests blocked)" if new_state else "Normal Mode Activated"
    }

@app.post("/api/control-center/clear-cache")
def clear_storage_cache():
    """Clear generated temporary audio and temporary caches."""
    result = clear_cache_storage()
    return {"status": "success", **result}

# ==========================================================================
# 2. LOCAL AI BRAIN ROUTES (WITH LOCAL PERSISTENT CACHING)
# ==========================================================================
@app.post("/api/ai/brain/explain")
def brain_explain_topic(payload: dict):
    topic = str(payload.get("topic", "")).strip()
    difficulty = str(payload.get("difficulty", "beginner"))
    language = str(payload.get("language", "en"))
    if not topic:
        raise HTTPException(400, "Topic is required.")
    return explain_topic(topic, difficulty, language)

@app.post("/api/ai/brain/flashcards")
def brain_generate_flashcards(payload: dict):
    text = str(payload.get("text", "")).strip()
    count = int(payload.get("count", 4))
    language = str(payload.get("language", "en"))
    if not text:
        raise HTTPException(400, "Text or topic is required.")
    return generate_flashcards(text, count, language)

@app.post("/api/ai/brain/quiz")
def brain_generate_quiz(payload: dict):
    text = str(payload.get("text", "")).strip()
    count = int(payload.get("count", 3))
    language = str(payload.get("language", "en"))
    if not text:
        raise HTTPException(400, "Text or topic is required.")
    return generate_practice_questions(text, count, language)

@app.post("/api/ai/brain/summarize")
def brain_summarize_notes(payload: dict):
    notes = str(payload.get("notes", "")).strip()
    language = str(payload.get("language", "en"))
    if not notes:
        raise HTTPException(400, "Notes are required to summarize.")
    return summarize_notes(notes, language)

@app.post("/api/ai/brain/kannada-bilingual")
def brain_kannada_bilingual(payload: dict):
    concept = str(payload.get("concept", "")).strip()
    details = str(payload.get("details", "")).strip()
    return get_kannada_bilingual_explanation(concept, details)

# ==========================================================================
# 3. OFFLINE CAMERA & PDF TUTOR ROUTES
# ==========================================================================
@app.post("/api/ocr/extract-pdf")
async def handle_pdf_extraction(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are supported.")
    contents = await file.read()
    result = extract_text_from_pdf(contents)
    if not result.get("success"):
        raise HTTPException(500, f"Failed to extract PDF: {result.get('error')}")
    return result

@app.post("/api/ocr/extract-image")
async def handle_image_extraction(file: UploadFile = File(...), prompt: str = Form(default="")):
    contents = await file.read()
    result = analyze_textbook_image(contents, prompt_text=prompt)
    return result

@app.post("/api/ocr/convert-to-study")
def handle_convert_study(payload: dict):
    text = str(payload.get("text", "")).strip()
    aids = payload.get("aids", ["flashcards", "quiz", "summary"])
    language = payload.get("language", "en")
    if not text:
        raise HTTPException(400, "Text is required.")
    return convert_content_to_study_aids(text, aids, language)

# ==========================================================================
# AUTHENTICATION ROUTES (LOGIN & REGISTER)
# ==========================================================================
@app.post("/api/auth/register")
def handle_register(payload: dict):
    username = payload.get("username", "")
    email = payload.get("email", "")
    password = payload.get("password", "")
    name = payload.get("name", "")
    language = payload.get("language", "en")
    level = payload.get("level", "beginner")

    try:
        result = register_user(username, email, password, name, language, level)
        return {"status": "success", "message": "Account created successfully!", **result}
    except ValueError as exc:
        raise HTTPException(400, str(exc))

@app.post("/api/auth/login")
def handle_login(payload: dict):
    ident = payload.get("username_or_email", "")
    password = payload.get("password", "")

    try:
        result = login_user(ident, password)
        return {"status": "success", "message": "Signed in successfully!", **result}
    except ValueError as exc:
        raise HTTPException(401, str(exc))

@app.get("/api/auth/me")
def handle_get_me(authorization: str | None = Header(None)):
    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split("Bearer ", 1)[1].strip()
    user = get_current_user(token)
    if not user:
        raise HTTPException(401, "Not authenticated or session expired.")
    return {"user": user}

# ==========================================================================
# NEURAL AI AUDIO (TTS) ROUTE
# ==========================================================================
@app.post("/api/tts")
def generate_ai_audio(payload: dict):
    text = str(payload.get("text", "")).strip()
    language = payload.get("language", "en")
    gender = payload.get("gender", "male")

    if not text:
        raise HTTPException(400, "Text is required for audio synthesis.")

    cache_key = hashlib.md5(f"{text}_{language}_{gender}".encode("utf-8")).hexdigest()[:16]
    target_mp3 = AUDIO_DIR / f"tts_{cache_key}.mp3"

    if not target_mp3.exists() or target_mp3.stat().st_size < 500:
        ok, note = synthesize(text, str(target_mp3), language=language, gender=gender)
    else:
        ok, note = True, "Cached Neural Voice"

    if not ok and not target_mp3.exists():
        raise HTTPException(500, f"Could not synthesize audio: {note}")

    return {
        "audio_url": f"/media/audio/{target_mp3.name}",
        "language": language,
        "source": note,
        "voice": NEURAL_VOICES.get(language, "en-US-ChristopherNeural")
    }

# ==========================================================================
# CORE LESSON & MEDIA ROUTES
# ==========================================================================
@app.get("/", response_class=HTMLResponse)
def home():
    return (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")

@app.get("/api/languages")
def get_languages():
    return {
        "supported": [
            {"code": "en", "name": "English", "native": "English", "voice": "en-US-ChristopherNeural"},
            {"code": "hi", "name": "Hindi", "native": "हिन्दी", "voice": "hi-IN-MadhurNeural"},
            {"code": "ta", "name": "Tamil", "native": "தமிழ்", "voice": "ta-IN-ValluvarNeural"},
            {"code": "te", "name": "Telugu", "native": "తెలుగు", "voice": "te-IN-MohanNeural"},
            {"code": "kn", "name": "Kannada", "native": "ಕನ್ನಡ", "voice": "kn-IN-GaganNeural"},
            {"code": "ml", "name": "Malayalam", "native": "മലയാളം", "voice": "ml-IN-MidhunNeural"},
            {"code": "bn", "name": "Bengali", "native": "বাংলা", "voice": "bn-IN-BashkarNeural"},
            {"code": "mr", "name": "Marathi", "native": "मराठी", "voice": "mr-IN-ManoharNeural"},
            {"code": "gu", "name": "Gujarati", "native": "ગુજરાતી", "voice": "gu-IN-NiranjanNeural"},
            {"code": "es", "name": "Spanish", "native": "Español", "voice": "es-ES-AlvaroNeural"},
            {"code": "fr", "name": "French", "native": "Français", "voice": "fr-FR-HenriNeural"},
            {"code": "de", "name": "German", "native": "Deutsch", "voice": "de-DE-ConradNeural"},
            {"code": "ja", "name": "Japanese", "native": "日本語", "voice": "ja-JP-KeitaNeural"}
        ]
    }

@app.get("/api/courses")
def list_courses():
    courses = get_course_catalog()
    return {"courses": courses, "total": len(courses)}

@app.post("/api/lesson")
def create_lesson(payload: dict):
    topic = str(payload.get("topic", "")).strip()[:200]
    level = payload.get("level", "beginner")
    language = payload.get("language", "en")
    seconds = int(payload.get("seconds", 45))
    if not topic:
        raise HTTPException(400, "Please enter a topic.")
    if level not in ("beginner", "intermediate"):
        level = "beginner"
    if language not in NEURAL_VOICES:
        language = "en"
    seconds = max(30, min(90, seconds))

    lesson = plan_with_ollama(topic, level, language, seconds)
    source = "Local Ollama Model" if lesson else "Neural Multilingual Generator"
    if lesson is None:
        lesson = generate_topic_aware_lesson(topic, level, language)
    
    lesson_id = uuid.uuid4().hex[:12]
    lesson["id"] = lesson_id

    full_narration = " ".join(s["narration"] for s in lesson.get("scenes", []))
    audio_path = OUT / f"{lesson_id}.mp3"
    audio_ok, audio_note = synthesize(full_narration, str(audio_path), language=language)
    lesson["audio_url"] = f"/media/{lesson_id}.mp3" if audio_ok else None
    lesson["audio_source"] = audio_note

    (OUT / f"{lesson_id}.json").write_text(
        json.dumps(lesson, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return {"id": lesson_id, "source": source, "audio_note": audio_note, "lesson": lesson}

@app.get("/api/download/json/{lesson_id}")
def download_lesson_json(lesson_id: str):
    path = OUT / f"{lesson_id}.json"
    if not path.exists():
        raise HTTPException(404, "Lesson file not found")
    return FileResponse(path, media_type="application/json", filename=f"lesson-{lesson_id}.json")

@app.post("/api/upload/json")
async def upload_json_lesson(file: UploadFile = File(...)):
    try:
        content = await file.read()
        parsed = json.loads(content.decode("utf-8"))
        lesson = Lesson.model_validate(parsed).model_dump()
        lesson_id = lesson.get("id") or f"import-{uuid.uuid4().hex[:8]}"
        lesson["id"] = lesson_id
        (OUT / f"{lesson_id}.json").write_text(
            json.dumps(lesson, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return {"id": lesson_id, "source": "imported JSON file", "lesson": lesson}
    except Exception as exc:
        raise HTTPException(400, f"Invalid JSON lesson file: {exc}")

@app.post("/api/upload/mp4")
async def upload_mp4_video(file: UploadFile = File(...)):
    if not file.filename.lower().endswith((".mp4", ".mov", ".m4v", ".webm")):
        raise HTTPException(400, "Only video files (.mp4, .mov, .m4v, .webm) are supported.")
    video_id = f"vid_{uuid.uuid4().hex[:10]}"
    ext = Path(file.filename).suffix or ".mp4"
    save_path = UPLOADS / f"{video_id}{ext}"
    try:
        contents = await file.read()
        save_path.write_bytes(contents)
        video_url = f"/media/uploads/{video_id}{ext}"
        return {
            "id": video_id,
            "filename": file.filename,
            "video_url": video_url,
            "size_kb": len(contents) // 1024,
            "message": "Video uploaded successfully!"
        }
    except Exception as exc:
        raise HTTPException(500, f"Failed to save video: {exc}")

@app.post("/api/export/{lesson_id}")
def export_lesson(lesson_id: str):
    path = OUT / f"{lesson_id}.json"
    if not path.exists():
        found = None
        for course in get_course_catalog():
            if course.get("id") == lesson_id:
                found = course
                break
        if found:
            path.write_text(json.dumps(found, ensure_ascii=False, indent=2), encoding="utf-8")
        else:
            raise HTTPException(404, "Lesson not found. Generate or select it again.")
    
    lesson = json.loads(path.read_text(encoding="utf-8"))
    
    audio_mp3 = OUT / f"{lesson_id}.mp3"
    audio_wav = OUT / f"{lesson_id}.wav"
    audio_target = audio_mp3 if audio_mp3.exists() else audio_wav

    if not audio_target.exists():
        narration = " ".join(s["narration"] for s in lesson["scenes"])
        ok, note = synthesize(narration, str(audio_mp3), lesson.get("language", "en"))
        if ok and audio_mp3.exists():
            audio_target = audio_mp3
        else:
            audio_target = None

    mp4_target = OUT / f"{lesson_id}.mp4"
    try:
        mp4 = make_mp4(lesson, str(mp4_target), str(audio_target) if audio_target and audio_target.exists() else None)
    except Exception as exc:
        raise HTTPException(500, str(exc))
    
    return {
        "download_url": f"/api/download/{lesson_id}",
        "video_url": f"/media/{lesson_id}.mp4",
        "audio": f"Neural AI voice ({lesson.get('language', 'en')})"
    }

@app.get("/api/lesson/python-loop")
def get_python_loop_lesson():
    """Return the special animated Python loop lesson with motion-specific scene types."""
    lesson_id = "python_loop_demo"
    loop_lesson = {
        "id": lesson_id,
        "title": "How does a Python loop work?",
        "level": "beginner",
        "language": "en",
        "category": "Programming",
        "scenes": [
            {
                "type": "title_card",
                "heading": "What is a Loop?",
                "narration": "A loop is a programming construct that repeats a block of instructions automatically, once for each item in a sequence, without you having to write the code multiple times."
            },
            {
                "type": "loop_cards",
                "heading": "Loop Running: 1 to 5",
                "narration": "Watch the loop count from one to five. Each number card appears in turn — the loop body runs once per card. After reaching five, the arrow sweeps back to show the repetition cycle."
            },
            {
                "type": "code_walkthrough",
                "heading": "Python Code Step by Step",
                "code": "for i in range(1, 6):\n    print(f'Number: {i}')\n    # Loop body runs here\n# Done! Printed 1 through 5",
                "highlight_lines": [1, 2, 3],
                "narration": "The for keyword starts the loop. range(1, 6) generates numbers one through five. Each iteration, i holds the current number and print shows it on screen. The indented block is the loop body."
            },
            {
                "type": "loop_arrow",
                "heading": "The Loop Back Arrow",
                "narration": "After executing the loop body, Python checks: are there more values? If yes, the flow arrow curves back to the top and the next iteration begins. This is what makes loops powerful — automatic repetition."
            },
            {
                "type": "diagram",
                "heading": "Loop Lifecycle Diagram",
                "items": ["Start", "Get next i", "Run body", "Check end?", "Done!"],
                "narration": "The loop lifecycle: start, get the next value of i, run the loop body, then check if there are more values. If yes, repeat. If no, the loop is done and execution continues after."
            }
        ],
        "quizzes": [
            {
                "id": 1,
                "question": "What values does range(1, 6) generate in Python?",
                "options": ["0, 1, 2, 3, 4", "1, 2, 3, 4, 5", "1, 2, 3, 4, 5, 6", "0 to 6"],
                "answer": 1,
                "explanation": "range(1, 6) starts at 1 and stops before 6, giving 1, 2, 3, 4, 5."
            },
            {
                "id": 2,
                "question": "What makes a loop different from writing the same code 5 times?",
                "options": ["Nothing, they are the same", "A loop runs automatically and is shorter to write", "A loop only works with numbers", "A loop cannot print"],
                "answer": 1,
                "explanation": "Loops automate repetition. Instead of copy-pasting code, you write it once and the loop runs it for each value."
            },
            {
                "id": 3,
                "question": "What does the loop arrow represent?",
                "options": ["Exiting the loop", "Going back to the top for another iteration", "Jumping to a function", "Printing the result"],
                "answer": 1,
                "explanation": "The loop back arrow shows that after each iteration, the loop returns to the top and checks if there is another value to process."
            }
        ],
        "flashcards": [
            {"front": "What is a loop?", "back": "A control structure that repeats a block of code for each item in a sequence.", "tip": "Think of it as automation."},
            {"front": "range(1, 6)", "back": "Generates 1, 2, 3, 4, 5 — starts at 1, stops before 6.", "tip": "The stop value is exclusive."},
            {"front": "Loop iteration", "back": "One single execution of the loop body.", "tip": "Each card appearing is one iteration."},
            {"front": "Loop arrow", "back": "The conceptual arrow that carries execution back to the loop header to start the next iteration.", "tip": "It is how repetition is implemented."}
        ],
        "summary": "A complete animated visual lesson on Python for-loops with moving number cards, animated code walkthrough, and loop arrow diagram."
    }

    # Save lesson JSON for export
    lesson_path = OUT / f"{lesson_id}.json"
    lesson_path.write_text(json.dumps(loop_lesson, ensure_ascii=False, indent=2), encoding="utf-8")

    # Generate narration audio
    narration = " ".join(s["narration"] for s in loop_lesson["scenes"])
    audio_path = OUT / f"{lesson_id}.mp3"
    if not audio_path.exists() or audio_path.stat().st_size < 500:
        synthesize(narration, str(audio_path), language="en")

    audio_url = f"/media/{lesson_id}.mp3" if audio_path.exists() else None
    return {"id": lesson_id, "source": "Built-in Python Loop Demo", "audio_note": "Neural AI Voice", "lesson": loop_lesson, "audio_url": audio_url}

@app.get("/api/download/{lesson_id}")
def download_lesson_mp4(lesson_id: str):
    path = OUT / f"{lesson_id}.mp4"
    if not path.exists():
        raise HTTPException(404, "MP4 video not found. Please export it first.")
    return FileResponse(path, media_type="video/mp4", filename=f"blu-lesson-{lesson_id}.mp4")

@app.get("/api/progress")
def get_user_progress_route(authorization: str | None = Header(None)):
    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split("Bearer ", 1)[1].strip()
    user = get_current_user(token)
    if user:
        return user
    
    prog_file = OUT / "guest_progress.json"
    if not prog_file.exists():
        return {"xp": 120, "level": 1, "streak_days": 3, "quizzes_taken": 1, "badges": ["Guest Explorer"], "history": []}
    return json.loads(prog_file.read_text(encoding="utf-8"))

@app.post("/api/quiz/submit")
def submit_quiz_result(payload: dict, authorization: str | None = Header(None)):
    lesson_id = payload.get("lesson_id", "unknown")
    lesson_title = payload.get("lesson_title", "General Quiz")
    score = payload.get("score", 0)
    total = payload.get("total", 1)
    strikes = payload.get("strikes", 0)
    time_taken = payload.get("time_taken", 0)
    
    earned_xp = score * 50
    if strikes == 0 and score > 0:
        earned_xp += 30
    elif strikes >= 3:
        earned_xp = max(0, earned_xp - 40)
        
    record = {
        "timestamp": int(time.time()),
        "lesson_id": lesson_id,
        "lesson_title": lesson_title,
        "score": score,
        "total": total,
        "percent": round((score / max(1, total)) * 100),
        "strikes": strikes,
        "time_taken_sec": time_taken,
        "earned_xp": earned_xp,
        "integrity_status": "Clean (Zero Tab Switches)" if strikes == 0 else f"{strikes} Tab Switch Strikes Recorded"
    }

    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split("Bearer ", 1)[1].strip()

    if token:
        updated = update_user_progress(token, {
            "xp": earned_xp,
            "history": [record],
            "quizzes_taken": 1
        })
        return {
            "status": "success",
            "record": record,
            "earned_xp": earned_xp,
            "total_xp": updated.get("xp"),
            "level": updated.get("level_num", 1),
            "badges": updated.get("badges", [])
        }

    prog_file = OUT / "guest_progress.json"
    curr = {"xp": 120, "level": 1, "streak_days": 3, "quizzes_taken": 1, "badges": ["First Lesson"], "history": []}
    if prog_file.exists():
        try:
            curr = json.loads(prog_file.read_text(encoding="utf-8"))
        except Exception:
            pass
    curr["xp"] = curr.get("xp", 120) + earned_xp
    curr["level"] = max(1, curr["xp"] // 100 + 1)
    curr["quizzes_taken"] = curr.get("quizzes_taken", 0) + 1
    curr["history"] = (curr.get("history", []) + [record])[-30:]
    prog_file.write_text(json.dumps(curr, indent=2, ensure_ascii=False), encoding="utf-8")

    return {
        "status": "success",
        "record": record,
        "earned_xp": earned_xp,
        "total_xp": curr["xp"],
        "level": curr["level"],
        "badges": curr["badges"]
    }
