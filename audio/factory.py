import os, re, json, time, requests
from gtts import gTTS
from google import genai
from google.genai import types
from google.oauth2 import service_account
from googleapiclient.discovery import build

print("=== AUDIO FACTORY START - NO DRIVE ===")
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
OPENROUTER_KEY = os.environ.get("OPENROUTER_API")
SERVICE_JSON_STR = os.environ.get("GOOGLE_SERVICE_JSON")
DOC_ID = os.environ.get("GOOGLE_DOC_ID")
SHEET_ID = os.environ.get("GOOGLE_SHEET_ID")

# Auth - Only Docs + Sheets, No Drive
service_info = json.loads(SERVICE_JSON_STR)
creds = service_account.Credentials.from_service_account_info(
    service_info,
    scopes=[
        'https://www.googleapis.com/auth/documents.readonly',
        'https://www.googleapis.com/auth/spreadsheets'
    ]
)
docs_service = build('docs', 'v1', credentials=creds)
sheets_service = build('sheets', 'v4', credentials=creds)

# Read Google Doc
doc = docs_service.documents().get(documentId=DOC_ID).execute()
full_text = "".join([elem['textRun']['content'] for el in doc.get('body').get('content', []) for elem in el.get('paragraph',{}).get('elements',[]) if 'textRun' in elem])
cases = re.split(r'Case \d+', full_text, flags=re.IGNORECASE)
case_text = cases[1][:3000] if len(cases) > 1 else full_text[:3000]
print(f"Case Found: {len(case_text)} chars")

prompt = f"""You are a professional Bangla Audiobook writer.
Convert this business case into natural emotional Bangla story for gTTS.
RULES: Pure Bangla unicode only, no English, 450-550 words, start with a hook question.
After script give:
TITLE_1: catchy bangla title max 8 words
TITLE_2: another title
KEYWORDS: 5 keywords comma separated
Case: {case_text}"""

bangla_script = None

# TRY 1: GEMINI
MODELS_TO_TRY = [
    ("v1beta", "gemini-3-flash-preview"),
    ("v1", "gemini-3.8-flash"),
    ("v1beta", "gemini-2.5-flash-lite"),
]

for api_ver, model_name in MODELS_TO_TRY:
    try:
        print(f"Trying: {api_ver}/{model_name}")
        client = genai.Client(api_key=GEMINI_KEY, http_options=types.HttpOptions(api_version=api_ver))
        response = client.models.generate_content(model=model_name, contents=prompt)
        bangla_script = response.text
        print(f"SUCCESS: {model_name}")
        break
    except Exception as e:
        print(f"Failed {model_name}: {str(e)[:200]}")
        time.sleep(5)
        continue

# TRY 2: OPENROUTER
if not bangla_script:
    print("Trying OpenRouter...")
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/aurangozebsajib/N8N_BizMap_Connector",
        "X-Title": "Bangla Audio Factory"
    }
    data = {
        "model": "inclusionai/ling-3.0-flash-fin:free",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 3000,
        "temperature": 0.7
    }
    resp = requests.post(url, headers=headers, json=data, timeout=90)
    if resp.status_code == 200:
        bangla_script = resp.json()['choices'][0]['message']['content']
        print("OPENROUTER SUCCESS")

if not bangla_script:
    raise Exception("All models failed")

# TTS
print("Generating MP3...")
title_match = re.search(r'TITLE_1:\s*(.*)', bangla_script)
raw_title = title_match.group(1).strip() if title_match else "Bangla_Audio"
title = re.sub(r'[^\w\s\u0980-\u09FF-]', '', raw_title)[:60].strip() or "Bangla_Audio_1"
tts_text = re.split(r'TITLE_1:', bangla_script)[0].strip()[:4000]

os.makedirs("output", exist_ok=True)
mp3_path = f"output/{title}.mp3"
gTTS(text=tts_text, lang='bn', slow=False).save(mp3_path)
print(f"MP3 Saved: {mp3_path}")

# Catbox - Temporary Storage for Video Merge (No Auth Needed)
catbox_link = "GitHub Artifact"
try:
    print("Uploading to Catbox...")
    with open(mp3_path, 'rb') as f:
        r = requests.post('https://catbox.moe/user/api.php',
                          data={'reqtype': 'fileupload'},
                          files={'fileToUpload': f}, timeout=60)
        if r.status_code == 200 and "files.catbox.moe" in r.text:
            catbox_link = r.text.strip()
            print(f"Catbox Link: {catbox_link}")
except Exception as e:
    print(f"Catbox failed, using Artifact only: {e}")

# Sheet Write - No Drive Link
try:
    t2 = re.search(r'TITLE_2:\s*(.*)', bangla_script)
    kw = re.search(r'KEYWORDS:\s*(.*)', bangla_script)
    row = [
        title,
        t2.group(1).strip() if t2 else "",
        kw.group(1).strip() if kw else "",
        tts_text[:2000],
        catbox_link,
        "Ready for Video Merge"
    ]
    sheets_service.spreadsheets().values().append(
        spreadsheetId=SHEET_ID, range="AI_Outputs!A:F",
        valueInputOption="USER_ENTERED", body={"values": [row]}
    ).execute()
    print("Sheet Updated")
except Exception as e:
    print(f"Sheet Error: {e}")

print("=== DONE - Audio ready in output/ ===")
