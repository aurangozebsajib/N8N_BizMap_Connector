# Bangla Factory - Audio Only (Your gTTS Version)

This repo has 2 folders as you asked:
- audio/ -> Works now (gTTS)
- video/ -> Empty, skip for now

## Structure
```
bangla-factory/
├── audio/
│   ├── factory.py (your gTTS version, 98 cases)
│   └── requirements.txt
├── video/ (empty placeholder)
└── .github/workflows/audio.yml
```

## Setup for GitHub (After Service Account)

### 1. Push files to GitHub
Create new repo `bangla-factory` -> upload:
- audio/factory.py
- audio/requirements.txt
- .github/workflows/audio.yml

### 2. Secrets (Repo -> Settings -> Secrets and variables -> Actions)
- GEMINI_API_KEY = from https://aistudio.google.com/app/apikey
- GOOGLE_SERVICE_JSON = full content of bangla-factory-xxxx.json file
- GOOGLE_DOC_ID = 1xWuKDdGCQtOYs1ya8S4qnvUJegjU6t4NnmjYEDK7N64
- GOOGLE_SHEET_ID = 1kkcvi6W1UGOuibnm0uGoylDmhFoEX2yqHAKYdpVI_9k

### 3. Run
- Go to Actions tab -> Audio Factory - Bangla gTTS -> Run workflow
OR
- From n8n mobile: HTTP Request POST to https://api.github.com/repos/YOUR_USERNAME/bangla-factory/dispatches
  Headers: Authorization: Bearer YOUR_PAT, Accept: application/vnd.github+json
  Body: {"event_type": "pick_case_study"}

### What it does
1. Reads Tracker -> Finds PENDING (Doc_Start_Index 0-97)
2. Reads Doc 1xWuK... -> Parses 98 cases using pattern CASE STUDY\s*[০-৯0-9]+
3. Calls Gemini to generate audio_script (Bangla, dialect rotation, CTA) + title_options + keywords (AFTER audio logic, as you asked)
4. Generates mp3 with YOUR gTTS lang='bn' slow=False
5. Auto-creates Drive folders n8n-bangla-tts/output if not exists, uploads mp3
6. Writes to AI_Outputs tab: audio_script, titles, keywords, drive link, READY_TO_POST
7. Updates Tracker to DONE

### Next Upgrade (After success)
Replace gTTS with edge-tts bn-BD-NabanitaNeural for natural female voice - just change 2 lines in factory.py
