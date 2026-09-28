# BRAIN PIPELINE v2

## What each job does
- **plan**: Reads ONE script from Google Doc STORY_STORAGE_DOC by date (BD UTC+6). Handles dialect conversion (rangpuri/barishal/old-dhaka/auto/none), splits into segments, classifies video_type, designs one consistent character. Writes output/plan.json + output/narration.txt.
- **audio**: Reads ONLY plan.json master_script_bn. Splits into <=400 char pieces, TTS via gTTS lang=bn, joins with pydub into MP3. Writes output/audio/<safe_label>.mp3 and audio_meta.json. Appends to Audio_Outputs.
- **video**: Generates reference image once (text-to-image), then per segment: text-animation always local, others via Hugging Face router with fallbacks (kenburns / textcard). Writes output/video/* + manifest.json. Appends to Video_Outputs. Exit 0 if at least one segment succeeded.

Audio and video run in parallel after plan. Same final script text from plan keeps sync.

## Doc format
```
Video 3 | 2026-10-02
Dialect: rangpuri
...Bangla story...
```
Heading regex: ^Video\s*(\d+)\s*[|:\-–—,]\s*(\d{4})-(\d{1,2})-(\d{1,2})$ (Bangla digits converted only for matching)
Optional second line Dialect: values none/rangpuri/barishal/old-dhaka/auto. Unknown -> none + warning. 12000 char limit.

## First-test order
1. Set secrets: GOOGLE_SERVICE_JSON, STORY_STORAGE_DOC, API_KEYS_SHEET, MODEL_STORAGE_SHEET
2. Fill sheets tabs per spec.
3. Run workflow with video_date empty (uses today BD), run_video=false, run_audio=true -> tests plan+audio.
4. Then run with both true.

## Owner manual steps
- Delete .github/workflows/audio.yml (old design). This repo now uses only brain.yml.
- If CHARACTER_MODE fixed, add brain/assets/host_reference.png and brain/assets/host_description.txt to repo.
- Ensure Model_Routing has rows for text-to-image, text-to-video, image-to-video sorted by priority.
- Fonts: workflow installs fonts-noto-core + libraqm. Local test needs NotoSansBengali.

## Secrets
Only GOOGLE_SERVICE_JSON, STORY_STORAGE_DOC, API_KEYS_SHEET, MODEL_STORAGE_SHEET. All API keys from sheets. No GOOGLE_DOC_ID, GOOGLE_SHEET_ID, GEMINI_API_KEY, OPENROUTER_API.

## Security
Keys masked via ::add-mask:: immediately after load. Gemini uses header x-goog-api-key, never ?key=. On failure only status logged. Keys never written to files/sheets.

## Assumptions
- Google Doc Tabs read via includeTabsContent=True and child tabs recursion, fallback to legacy body.
- Dialect auto picks random among three.
- TTS gTTS only, 2.5 wps for timing.
- HF endpoint https://router.huggingface.co/hf-inference/models/<model_id>
- image-to-video must include ref image every attempt (format A raw bytes + ?prompt=, format B base64). Never text-only.
- Local fallback default true with visible statuses fallback-kenburns, fallback-textcard, failed-local-render, failed-no-model-available, failed-no-ref.
- Text shaping requires Pillow with raqm; if missing, marked failed-local-render.
- Workflow uses always() for video condition so run_video=false still green.
