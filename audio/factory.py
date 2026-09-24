"""
Bangla Audio Factory - FINAL - Your gTTS Version
Location: audio/factory.py
Does: Sheet Tracker -> Doc -> Gemini Director -> gTTS -> Drive -> Sheet
98 cases, mixed pattern CASE STUDY 1 / CASE STUDY ১
"""

import os
import json
import re
import time
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
import google.generativeai as genai
from gtts import gTTS
from googleapiclient.http import MediaFileUpload

# --- CONFIG ---
DOC_ID = os.environ.get("GOOGLE_DOC_ID", "1xWuKDdGCQtOYs1ya8S4qnvUJegjU6t4NnmjYEDK7N64")
SHEET_ID = os.environ.get("GOOGLE_SHEET_ID", "1kkcvi6W1UGOuibnm0uGoylDmhFoEX2yqHAKYdpVI_9k")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GOOGLE_SERVICE_JSON = os.environ.get("GOOGLE_SERVICE_JSON")
DRIVE_ROOT_FOLDER = "n8n-bangla-tts"
DRIVE_OUTPUT_FOLDER = "output"

SCOPES = [
    "https://www.googleapis.com/auth/documents.readonly",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

def get_clients():
    creds_dict = json.loads(GOOGLE_SERVICE_JSON)
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    docs_service = build('docs', 'v1', credentials=creds)
    drive_service = build('drive', 'v3', credentials=creds)
    gc = gspread.authorize(creds)
    return docs_service, drive_service, gc

def get_doc_text(docs_service, doc_id):
    doc = docs_service.documents().get(documentId=doc_id).execute()
    text = ""
    for elem in doc.get('body', {}).get('content', []):
        if 'paragraph' in elem:
            for pe in elem['paragraph'].get('elements', []):
                if 'textRun' in pe:
                    text += pe['textRun'].get('content', '')
    return text

def parse_cases(full_text):
    # Your pattern - mixed English 1,2,3 and Bangla ১,২,৩ - Found 98 cases
    pattern = r"CASE STUDY\s*[০-৯0-9]+"
    parts = re.split(pattern, full_text)
    cases = []
    for p in parts:
        p = p.strip()
        if len(p) > 200: # valid case study
            title = p.split('\n')[0].strip()[:120]
            cases.append({"title": title, "full_text": p})
    return cases

def get_next_pending(gc, sheet_id):
    sh = gc.open_by_key(sheet_id)
    ws = sh.worksheet("Tracker")
    records = ws.get_all_records()
    for idx, row in enumerate(records, start=2):
        status = str(row.get('Status','')).upper()
        if status != 'DONE':
            return row, idx, sh
    return None, None, sh

def get_or_create_drive_folder(drive_service, folder_name, parent_id=None):
    # Search folder
    q = f"mimeType='application/vnd.google-apps.folder' and name='{folder_name}' and trashed=false"
    if parent_id:
        q += f" and '{parent_id}' in parents"
    results = drive_service.files().list(q=q, fields="files(id, name)").execute()
    if results['files']:
        print(f"Folder found: {folder_name} -> {results['files'][0]['id']}")
        return results['files'][0]['id']
    # Create
    metadata = {'name': folder_name, 'mimeType': 'application/vnd.google-apps.folder'}
    if parent_id:
        metadata['parents'] = [parent_id]
    folder = drive_service.files().create(body=metadata, fields='id').execute()
    print(f"Folder created: {folder_name} -> {folder.get('id')}")
    return folder.get('id')

def upload_to_drive(drive_service, file_path, root_name, output_name):
    # Auto-create structure: n8n-bangla-tts/output
    root_id = get_or_create_drive_folder(drive_service, root_name)
    output_id = get_or_create_drive_folder(drive_service, output_name, parent_id=root_id)
    
    file_metadata = {'name': os.path.basename(file_path), 'parents': [output_id]}
    media = MediaFileUpload(file_path, resumable=True)
    file = drive_service.files().create(body=file_metadata, media_body=media, fields='id, webViewLink').execute()
    print(f"Uploaded: {file.get('webViewLink')}")
    return file.get('id'), file.get('webViewLink')

# === YOUR GEMINI DIRECTOR PROMPT - KEEPING YOUR VERSION + DIALECT ROTATION ===
GEMINI_PROMPT = """
You are Bangla Case Study Script Writer for TTS.

INPUT CASE STUDY:
{case_text}

Dialect for today: {dialect} (use 20% local words naturally, but keep TTS readable)

YOUR TASK: Write audio_script in Bangla (400-500 chars, no English).
Rules:
- 100% Bangla, convert customer->কাস্টমার, working capital->কাজের পুঁজি, business->ব্যবসা, etc.
- Hook first 5 sec shocking, story: Problem -> Old Thinking -> New Thinking/Result
- 80% standard Bangla + 20% {dialect} local flavor (বরিশাল example: মুই, মনু, কইতে আছি)
- Sentences short for gTTS.
- End MUST be exactly: 'এমন আরো বিজনেস কেস স্টাডি জানতে পিন কমেন্টে দেওয়া PDF টা পড়ুন।'
- Also generate: title_options (3 viral titles), description, keywords (15)

Return ONLY JSON:
{{
  "audio_script": "...",
  "title_options": ["title1", "title2", "title3"],
  "description": "YouTube description Bangla",
  "keywords": ["keyword1", "keyword2", ...]
}}
"""

DIALECTS = ["Chittagong", "Barishal", "Sylheti", "Cox's Bazar", "Noakhali"]

def main():
    print("=== AUDIO FACTORY START ===")
    docs_service, drive_service, gc = get_clients()
    
    # 1. Next pending
    next_row, row_idx, sh = get_next_pending(gc, SHEET_ID)
    if not next_row:
        print("No PENDING found - all 98 done!")
        return
    
    print(f"Next: Chapter {next_row.get('Chapter')} Case {next_row.get('Case_No')} Index {next_row.get('Doc_Start_Index')}")
    case_index = int(next_row.get('Doc_Start_Index', 0))
    dialect = DIALECTS[case_index % len(DIALECTS)]
    
    # 2. Parse Doc
    full_text = get_doc_text(docs_service, DOC_ID)
    cases = parse_cases(full_text)
    print(f"Total cases in Doc: {len(cases)} (expected 98)")
    
    if case_index >= len(cases):
        print(f"Index {case_index} out of range")
        return
    
    selected = cases[case_index]
    print(f"Selected Title: {selected['title'][:80]}")
    
    # 3. Gemini - Generate audio script + title + keywords AFTER video logic (you said title/keywords after video, but video skipped, so now after audio script)
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash') # stable, free
    prompt = GEMINI_PROMPT.format(case_text=selected['full_text'][:3500], dialect=dialect)
    
    response = model.generate_content(prompt)
    text_resp = response.text.strip()
    text_resp = re.sub(r'^```json|```$', '', text_resp, flags=re.MULTILINE).strip()
    
    try:
        result = json.loads(text_resp)
    except:
        m = re.search(r'\{.*\}', text_resp, re.DOTALL)
        result = json.loads(m.group(0)) if m else {}
    
    audio_script = result.get('audio_script', selected['full_text'][:500]) # fallback
    title_options = result.get('title_options', [])
    description = result.get('description', '')
    keywords = result.get('keywords', [])
    
    print(f"Audio Script: {audio_script[:120]}...")
    
    # 4. YOUR gTTS VERSION - Keep as you had
    os.makedirs('output', exist_ok=True)
    audio_filename = f"audio_ch{next_row.get('Chapter')}_case{next_row.get('Case_No')}_{datetime.now().strftime('%Y%m%d')}.mp3"
    audio_path = f"output/{audio_filename}"
    
    # Your original code: gTTS lang='bn' slow=False
    tts = gTTS(text=audio_script, lang='bn', slow=False)
    tts.save(audio_path)
    print(f"Audio saved with gTTS: {audio_path}")
    
    # 5. Upload to Drive - auto-create folders
    file_id, web_link = upload_to_drive(drive_service, audio_path, DRIVE_ROOT_FOLDER, DRIVE_OUTPUT_FOLDER)
    
    # 6. Write to AI_Outputs tab
    ws_out = sh.worksheet("AI_Outputs")
    ws_out.append_row([
        datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        next_row.get('Chapter',''),
        next_row.get('Case_No',''),
        selected['title'],
        selected['full_text'][:5000],
        audio_script,
        "", # Video JSON empty (video skipped)
        ", ".join(title_options),
        description,
        ", ".join(keywords),
        web_link, # Audio link
        "", # Video link empty
        "READY_TO_POST"
    ])
    
    # 7. Update Tracker to DONE
    ws_tracker = sh.worksheet("Tracker")
    ws_tracker.update_cell(row_idx, 4, "DONE") # Status
    ws_tracker.update_cell(row_idx, 5, datetime.now().strftime('%Y-%m-%d %H:%M:%S')) # Last_Picked_Date
    
    # Update Config
    try:
        ws_config = sh.worksheet("Config")
        ws_config.update_cell(5, 2, datetime.now().isoformat())
    except:
        pass
    
    print("=== AUDIO FACTORY DONE ===")
    print(f"Drive Link: {web_link}")
    print(f"Title Options: {title_options}")

if __name__ == "__main__":
    main()
