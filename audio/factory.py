import os, re, json
from gtts import gTTS
from google import genai
from google.genai import types
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

print("=== AUDIO FACTORY START ===")
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
SERVICE_JSON_STR = os.environ.get("GOOGLE_SERVICE_JSON")
DOC_ID = os.environ.get("GOOGLE_DOC_ID")
SHEET_ID = os.environ.get("GOOGLE_SHEET_ID")

service_info = json.loads(SERVICE_JSON_STR)
creds = service_account.Credentials.from_service_account_info(service_info, scopes=['https://www.googleapis.com/auth/documents.readonly','https://www.googleapis.com/auth/spreadsheets','https://www.googleapis.com/auth/drive'])
docs_service = build('docs', 'v1', credentials=creds)
sheets_service = build('sheets', 'v4', credentials=creds)
drive_service = build('drive', 'v3', credentials=creds)

doc = docs_service.documents().get(documentId=DOC_ID).execute()
full_text = "".join([elem['textRun']['content'] for el in doc.get('body').get('content', []) for elem in el.get('paragraph',{}).get('elements',[]) if 'textRun' in elem])
cases = re.split(r'Case \d+', full_text, flags=re.IGNORECASE)
case_text = cases[1][:3000] if len(cases) > 1 else full_text[:3000]
print(f"Case Found: {len(case_text)} chars")

# === AUTO MODEL FINDER ===
client = genai.Client(api_key=GEMINI_KEY, http_options=types.HttpOptions(api_version='v1'))

PREFERRED_MODELS = [
    "gemini-3.8-flash",
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-2.5-flash",
    "gemini-flash-latest",
    "gemini-pro-latest"
]

prompt = f"""
You are a professional Bangla Audiobook writer.
Convert this business case into natural emotional Bangla story for gTTS.
RULES: Pure Bangla unicode, 450-550 words, start with hook.
After script give:
TITLE_1: catchy bangla title max 8 words
TITLE_2: another title
KEYWORDS: 5 keywords comma separated
Case: {case_text}
"""

bangla_script = None
last_error = None
for model_name in PREFERRED_MODELS:
    try:
        print(f"Trying model: {model_name}...")
        response = client.models.generate_content(model=model_name, contents=prompt)
        bangla_script = response.text
        print(f"SUCCESS with {model_name}")
        break
    except Exception as e:
        print(f"Failed {model_name}: {str(e)[:150]}")
        last_error = e
        continue

if not bangla_script:
    raise Exception(f"All models failed. Last error: {last_error}")

print(bangla_script[:300])
title_match = re.search(r'TITLE_1:\s*(.*)', bangla_script)
title = re.sub(r'[^\w\s\u0980-\u09FF-]', '', title_match.group(1).strip() if title_match else "Bangla_Business_Audio")[:60]
tts_text = re.split(r'TITLE_1:', bangla_script)[0].strip()[:4000]

os.makedirs("output", exist_ok=True)
mp3_path = f"output/{title}.mp3"
gTTS(text=tts_text, lang='bn', slow=False).save(mp3_path)
print(f"MP3 saved")

# Drive Upload
folder_name = "n8n-bangla-tts"
q = f"mimeType='application/vnd.google-apps.folder' and name='{folder_name}' and trashed=false"
folders = drive_service.files().list(q=q, fields="files(id)").execute().get('files', [])
folder_id = folders[0]['id'] if folders else drive_service.files().create(body={'name': folder_name, 'mimeType': 'application/vnd.google-apps.folder'}, fields='id').execute().get('id')
file = drive_service.files().create(body={'name': os.path.basename(mp3_path), 'parents': [folder_id]}, media_body=MediaFileUpload(mp3_path, mimetype='audio/mpeg'), fields='id, webViewLink').execute()
drive_link = file.get('webViewLink')
print(f"Uploaded: {drive_link}")

# Sheet
try:
    t2 = re.search(r'TITLE_2:\s*(.*)', bangla_script)
    kw = re.search(r'KEYWORDS:\s*(.*)', bangla_script)
    row = [title, t2.group(1).strip() if t2 else "", kw.group(1).strip() if kw else "", tts_text[:5000], drive_link, "Auto Model"]
    sheets_service.spreadsheets().values().append(spreadsheetId=SHEET_ID, range="AI_Outputs!A:F", valueInputOption="USER_ENTERED", body={"values": [row]}).execute()
except Exception as e:
    print(f"Sheet error: {e}")

print("=== AUDIO FACTORY DONE ===")
