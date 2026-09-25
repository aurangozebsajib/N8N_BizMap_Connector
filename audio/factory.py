import os
import re
import json
from gtts import gTTS
from google import genai
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

print("=== AUDIO FACTORY START ===")

# Secrets
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
SERVICE_JSON_STR = os.environ.get("GOOGLE_SERVICE_JSON")
DOC_ID = os.environ.get("GOOGLE_DOC_ID")
SHEET_ID = os.environ.get("GOOGLE_SHEET_ID")

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
print(f"Reading Doc: {DOC_ID}")
doc = docs_service.documents().get(documentId=DOC_ID).execute()
content = doc.get('body').get('content')
full_text = ""
for element in content:
    if 'paragraph' in element:
        for elem in element['paragraph']['elements']:
            if 'textRun' in elem:
                full_text += elem['textRun']['content']

# Simple parsing - Chapter 1 Case 1
# Find first case
match = re.search(r'Case \d+.*?\n(.*?)(?:Case \d+|$)', full_text, re.DOTALL | re.IGNORECASE)
case_text = match.group(1).strip() if match else full_text[:2000]
print(f"Selected Title: {case_text[:80]}")

# 2. Gemini - New SDK
print("Calling Gemini...")
client = genai.Client(api_key=GEMINI_KEY)
prompt = f"""
You are a professional Bangla Audiobook writer. Convert this business case into a natural, emotional, story-telling Bangla audio script for gTTS.

Rules:
- Pure Bangla (no English)
- 400-500 words
- Start with hook
- Conversational tone

Case:
{case_text[:3000]}

Also give:
TITLE_1: (catchy)
TITLE_2: (catchy)
KEYWORDS: 5 keywords comma separated
"""

response = client.models.generate_content(
    model="gemini-2.0-flash",
    contents=prompt
)
bangla_script = response.text
print("Gemini done")

# Extract Title etc
title_match = re.search(r'TITLE_1:\s*(.*)', bangla_script)
title = title_match.group(1).strip() if title_match else "Bangla Business Audio"

# 3. gTTS
print("Generating MP3...")
tts = gTTS(text=bangla_script, lang='bn', slow=False)
os.makedirs("output", exist_ok=True)
mp3_path = f"output/{title[:30].replace('/', '_')}.mp3"
tts.save(mp3_path)

# 4. Upload to Drive
print("Uploading to Drive...")
# Find or create folder
folder_name = "n8n-bangla-tts"
query = f"mimeType='application/vnd.google-apps.folder' and name='{folder_name}' and trashed=false"
folders = drive_service.files().list(q=query, fields="files(id, name)").execute().get('files', [])
if folders:
    folder_id = folders[0]['id']
    print(f"Folder found: {folder_id}")
else:
    folder_metadata = {'name': folder_name, 'mimeType': 'application/vnd.google-apps.folder'}
    folder = drive_service.files().create(body=folder_metadata, fields='id').execute()
    folder_id = folder.get('id')
    print(f"Folder created: {folder_id}")

file_metadata = {'name': os.path.basename(mp3_path), 'parents': [folder_id]}
media = MediaFileUpload(mp3_path, mimetype='audio/mpeg')
file = drive_service.files().create(body=file_metadata, media_body=media, fields='id, webViewLink').execute()
drive_link = file.get('webViewLink')
print(f"Uploaded: {drive_link}")

# 5. Write to Sheet
print("Writing to Sheet...")
row = [title, bangla_script[:5000], drive_link, "Chapter 1 Case 1"]
sheets_service.spreadsheets().values().append(
    spreadsheetId=SHEET_ID,
    range="AI_Outputs!A:D",
    valueInputOption="USER_ENTERED",
    body={"values": [row]}
).execute()

print("=== AUDIO FACTORY DONE ===")
print(f"Drive Link: {drive_link}")
