import os
import re
import json
from gtts import gTTS
from google import genai
from google.genai import types
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

print("=== AUDIO FACTORY START ===")

# ENV
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
SERVICE_JSON_STR = os.environ.get("GOOGLE_SERVICE_JSON")
DOC_ID = os.environ.get("GOOGLE_DOC_ID")
SHEET_ID = os.environ.get("GOOGLE_SHEET_ID")

if not all([GEMINI_KEY, SERVICE_JSON_STR, DOC_ID, SHEET_ID]):
    raise ValueError("Secrets missing: GEMINI_API_KEY, GOOGLE_SERVICE_JSON, GOOGLE_DOC_ID, GOOGLE_SHEET_ID")

# Auth
service_info = json.loads(SERVICE_JSON_STR)
creds = service_account.Credentials.from_service_account_info(
    service_info,
    scopes=[
        'https://www.googleapis.com/auth/documents.readonly',
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ]
)

docs_service = build('docs', 'v1', credentials=creds)
sheets_service = build('sheets', 'v4', credentials=creds)
drive_service = build('drive', 'v3', credentials=creds)

# 1. Read Doc
print(f"Reading Doc: {DOC_ID[:10]}...")
doc = docs_service.documents().get(documentId=DOC_ID).execute()
full_text = ""
for element in doc.get('body').get('content', []):
    if 'paragraph' in element:
        for elem in element['paragraph']['elements']:
            if 'textRun' in elem:
                full_text += elem['textRun']['content']

print(f"Doc length: {len(full_text)} chars")
# Extract first case
cases = re.split(r'Case \d+', full_text, flags=re.IGNORECASE)
case_text = cases[1][:3000] if len(cases) > 1 else full_text[:3000]
print(f"Selected Title: {case_text[:100].strip()}")

# 2. Gemini - FIXED with v1 and 2.5-flash
print("Calling Gemini...")
client = genai.Client(
    api_key=GEMINI_KEY,
    http_options=types.HttpOptions(api_version='v1')
)

prompt = f"""
You are a professional Bangla Audiobook writer for business stories.
Convert this business case into a natural, emotional, story-telling Bangla audio script for gTTS.

RULES:
- Pure Bangla (Bangla unicode only, no English words)
- 450-550 words
- Start with a hook question
- Conversational, like you are telling a story to a friend
- Keep business lesson clear

After the script, on new lines, give:
TITLE_1: catchy bangla title (max 8 words)
TITLE_2: another catchy title
KEYWORDS: 5 keywords, comma separated

Case:
{case_text}
"""

response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=prompt
)
bangla_script = response.text
print("Gemini done")
print(bangla_script[:300])

# Extract metadata
title_match = re.search(r'TITLE_1:\s*(.*)', bangla_script)
title = title_match.group(1).strip() if title_match else "Bangla Business Audio"
title = re.sub(r'[^\w\s\u0980-\u09FF-]', '', title)[:60] # clean for filename
if not title:
    title = "Bangla_Audio_Chapter1"

# Remove TITLE lines from script for TTS
tts_text = re.split(r'TITLE_1:', bangla_script)[0].strip()
tts_text = tts_text[:4000] # gTTS limit

# 3. gTTS
print("Generating MP3...")
os.makedirs("output", exist_ok=True)
mp3_path = f"output/{title}.mp3"
tts = gTTS(text=tts_text, lang='bn', slow=False)
tts.save(mp3_path)
print(f"MP3 saved: {mp3_path}")

# 4. Upload to Drive
print("Uploading to Drive...")
folder_name = "n8n-bangla-tts"
query = f"mimeType='application/vnd.google-apps.folder' and name='{folder_name}' and trashed=false"
folders = drive_service.files().list(q=query, fields="files(id, name)").execute().get('files', [])
if folders:
    folder_id = folders[0]['id']
else:
    folder_metadata = {'name': folder_name, 'mimeType': 'application/vnd.google-apps.folder'}
    folder = drive_service.files().create(body=folder_metadata, fields='id').execute()
    folder_id = folder.get('id')

file_metadata = {'name': os.path.basename(mp3_path), 'parents': [folder_id]}
media = MediaFileUpload(mp3_path, mimetype='audio/mpeg')
file = drive_service.files().create(body=file_metadata, media_body=media, fields='id, webViewLink').execute()
drive_link = file.get('webViewLink')
print(f"Uploaded: {drive_link}")

# 5. Write to Sheet
print("Writing to Sheet...")
try:
    # Clean script for sheet
    title2_match = re.search(r'TITLE_2:\s*(.*)', bangla_script)
    title2 = title2_match.group(1).strip() if title2_match else ""
    kw_match = re.search(r'KEYWORDS:\s*(.*)', bangla_script)
    keywords = kw_match.group(1).strip() if kw_match else ""

    row = [title, title2, keywords, tts_text[:5000], drive_link, "Chapter 1 Case 1"]
    sheets_service.spreadsheets().values().append(
        spreadsheetId=SHEET_ID,
        range="AI_Outputs!A:F",
        valueInputOption="USER_ENTERED",
        body={"values": [row]}
    ).execute()
    print("Sheet updated")
except Exception as e:
    print(f"Sheet write failed (non-critical): {e}")

print("=== AUDIO FACTORY DONE ===")
print(f"Drive Link: {drive_link}")
