import os, re, json, time, random, requests
from gtts import gTTS
from google import genai
from google.genai import types
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

print("=== AUDIO FACTORY START (No Workspace Mode) ===")
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
OPENROUTER_KEY = os.environ.get("OPENROUTER_API")
SERVICE_JSON_STR = os.environ.get("GOOGLE_SERVICE_JSON")
DOC_ID = os.environ.get("GOOGLE_DOC_ID")
SHEET_ID = os.environ.get("GOOGLE_SHEET_ID")

service_info = json.loads(SERVICE_JSON_STR)
creds = service_account.Credentials.from_service_account_info(
    service_info,
    scopes=['https://www.googleapis.com/auth/documents.readonly','https://www.googleapis.com/auth/spreadsheets','https://www.googleapis.com/auth/drive']
)
docs_service = build('docs', 'v1', credentials=creds)
sheets_service = build('sheets', 'v4', credentials=creds)

# Read Doc
doc = docs_service.documents().get(documentId=DOC_ID).execute()
full_text = "".join([elem['textRun']['content'] for el in doc.get('body').get('content', []) for elem in el.get('paragraph',{}).get('elements',[]) if 'textRun' in elem])
cases = re.split(r'Case \d+', full_text, flags=re.IGNORECASE)
case_text = cases[1][:3000] if len(cases) > 1 else full_text[:3000]
print(f"Case length: {len(case_text)}")

prompt = f"""You are a professional Bangla Audiobook writer.
Convert this business case into natural emotional Bangla story for gTTS.
RULES: Pure Bangla unicode only, no English, 450-550 words, start with a hook question, conversational story telling.
After script give:
TITLE_1: catchy bangla title max 8 words
TITLE_2: another title
KEYWORDS: 5 keywords comma separated
Case: {case_text}"""

bangla_script = None

# GEMINI TRY
MODELS_TO_TRY = [
    ("v1beta", "gemini-3-flash-preview"),
    ("v1", "gemini-3.8-flash"),
    ("v1beta", "gemini-3.8-flash"),
    ("v1beta", "gemini-2.5-flash-lite"),
]

for api_ver, model_name in MODELS_TO_TRY:
    for attempt in range(2):
        try:
            print(f"Trying GEMINI {api_ver}/{model_name}")
            client = genai.Client(api_key=GEMINI_KEY, http_options=types.HttpOptions(api_version=api_ver))
            response = client.models.generate_content(model=model_name, contents=prompt)
            bangla_script = response.text
            print(f"SUCCESS: {model_name}")
            break
        except Exception as e:
            err = str(e)
            if "503" in err or "UNAVAILABLE" in err:
                print(f"503 overload, waiting 15s...")
                time.sleep(15)
                continue
            print(f"Failed {model_name}: {err[:200]}")
            break
    if bangla_script:
        break

# OPENROUTER FALLBACK
if not bangla_script:
    print("Gemini failed, switching to OPENROUTER...")
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
    resp = requests.post(url, headers=headers, json=data, timeout=60)
    if resp.status_code == 200:
        bangla_script = resp.json()['choices'][0]['message']['content']
        print("OPENROUTER SUCCESS")
    else:
        raise Exception(f"OpenRouter failed: {resp.text[:500]}")

# TTS
print("Generating MP3...")
title_match = re.search(r'TITLE_1:\s*(.*)', bangla_script)
raw_title = title_match.group(1).strip() if title_match else "Bangla_Business_Audio"
title = re.sub(r'[^\w\s\u0980-\u09FF-]', '', raw_title)[:60].strip() or "Bangla_Audio_1"
tts_text = re.split(r'TITLE_1:', bangla_script)[0].strip()[:4000]

os.makedirs("output", exist_ok=True)
mp3_path = f"output/{title}.mp3"
gTTS(text=tts_text, lang='bn', slow=False).save(mp3_path)
print(f"MP3 saved: {mp3_path}")

# SHEET WRITE - No Drive Link Needed
drive_link = f"GitHub Artifact - Download from Actions tab - {title}.mp3"
try:
    t2 = re.search(r'TITLE_2:\s*(.*)', bangla_script)
    kw = re.search(r'KEYWORDS:\s*(.*)', bangla_script)
    row = [title, t2.group(1).strip() if t2 else "", kw.group(1).strip() if kw else "", tts_text[:4000], drive_link, "Generated without Shared Drive"]
    sheets_service.spreadsheets().values().append(
        spreadsheetId=SHEET_ID, range="AI_Outputs!A:F",
        valueInputOption="USER_ENTERED", body={"values": [row]}
    ).execute()
    print("Sheet updated")
except Exception as e:
    print(f"Sheet error: {e}")

print("=== AUDIO FACTORY DONE ===")
print(f"File ready: {mp3_path}")
