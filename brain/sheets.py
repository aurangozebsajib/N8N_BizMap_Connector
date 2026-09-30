import os
import json
import brain.config as cfg

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly"
]

def get_gspread_client():
    raw_sa = os.environ.get(cfg.GOOGLE_SERVICE_JSON, "")
    if not raw_sa:
        print("⚠️ Warning: GOOGLE_SERVICE_JSON environment variable not set.")
        return None
    try:
        from google.oauth2.service_account import Credentials
        import gspread
        info = json.loads(raw_sa)
        creds = Credentials.from_service_account_info(info, scopes=SCOPES)
        return gspread.authorize(creds)
    except Exception as e:
        print(f"❌ Error initializing gspread client: {e}")
        return None

def load_hf_keys():
    """
    Loads Hugging Face API keys from Google Sheet:
    - Sheet identified by API_KEYS_SHEET (can be Sheet ID or title "Api_keys_Sheet")
    - Tab: "Video API"
    Returns a list of dicts: [{"key_id": "...", "api_key_value": "..."}]
    """
    keys = []
    
    # 1. First check environment variable HF_TOKEN or HUGGINGFACE_API_KEY as primary/fallback
    env_token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_API_KEY")
    if env_token:
        keys.append({"key_id": "ENV_HF_TOKEN", "api_key_value": env_token.strip()})
        print(f"🔑 Loaded 1 Hugging Face key from environment variable.")

    sheet_identifier = os.environ.get(cfg.API_KEYS_SHEET, "Api_keys_Sheet")
    client = get_gspread_client()
    
    if client and sheet_identifier:
        spreadsheet = None
        # Try open by key first
        try:
            spreadsheet = client.open_by_key(sheet_identifier)
        except Exception:
            # If not a key, try open by name
            try:
                spreadsheet = client.open(sheet_identifier)
            except Exception as e:
                print(f"⚠️ Could not open Google Sheet by key or name '{sheet_identifier}': {e}")
                
        if spreadsheet:
            # Find the "Video API" worksheet (case-insensitive search)
            target_ws = None
            for ws in spreadsheet.worksheets():
                cleaned_title = ws.title.strip().lower().replace("_", " ")
                if cleaned_title in ("video api", "videoapi", "hf keys", "huggingface"):
                    target_ws = ws
                    break
            
            if not target_ws:
                # If specific tab not found, try to open "Video API" directly or first worksheet
                try:
                    target_ws = spreadsheet.worksheet("Video API")
                except Exception:
                    print("⚠️ Tab 'Video API' not found by name. Checking all available worksheets...")
                    target_ws = spreadsheet.sheet1

            if target_ws:
                print(f"📊 Reading Hugging Face keys from Google Sheet tab: '{target_ws.title}'...")
                try:
                    all_records = target_ws.get_all_records()
                    for idx, row in enumerate(all_records, start=2):
                        # Detect key value from various possible column names
                        token_val = None
                        for col_name in ["api_key_value", "api_key", "key", "token", "hf_token", "hf_key", "secret"]:
                            for k in row.keys():
                                if k.strip().lower() == col_name and str(row[k]).strip():
                                    token_val = str(row[k]).strip()
                                    break
                            if token_val:
                                break
                                
                        # If get_all_records didn't catch header, fallback to value scan
                        if not token_val:
                            for val in row.values():
                                val_str = str(val).strip()
                                if val_str.startswith("hf_"):
                                    token_val = val_str
                                    break
                                    
                        # Check status column if exists
                        status_val = str(row.get("status", "")).strip().lower()
                        if status_val in ("inactive", "disabled", "dead", "banned"):
                            continue
                            
                        if token_val and token_val not in [k["api_key_value"] for k in keys]:
                            key_id = str(row.get("key_id", f"sheet_row_{idx}"))
                            keys.append({"key_id": key_id, "api_key_value": token_val})
                            
                    print(f"✅ Successfully loaded {len(keys)} active Hugging Face keys from Google Sheet!")
                except Exception as e:
                    print(f"❌ Error reading records from worksheet: {e}")
                    # Fallback: read raw row values
                    try:
                        raw_values = target_ws.get_all_values()
                        for idx, row in enumerate(raw_values[1:], start=2):
                            for cell in row:
                                cell_str = str(cell).strip()
                                if cell_str.startswith("hf_") and cell_str not in [k["api_key_value"] for k in keys]:
                                    keys.append({"key_id": f"row_{idx}", "api_key_value": cell_str})
                        print(f"✅ Extracted {len(keys)} keys via raw cell scan.")
                    except Exception as err2:
                        print(f"❌ Raw value scan failed: {err2}")

    if not keys:
        print("⚠️ Warning: No Hugging Face API keys could be loaded. Local rendering fallback will be used.")
    return keys

def load_model_routing():
    """
    Default model priority list for text-to-image, text-to-video, image-to-video
    """
    return {
        "text-to-image": [
            {"model_id": "black-forest-labs/FLUX.1-schnell", "priority": 1},
            {"model_id": "stabilityai/stable-diffusion-xl-base-1.0", "priority": 2},
            {"model_id": "runwayml/stable-diffusion-v1-5", "priority": 3}
        ],
        "text-to-video": [
            {"model_id": "ali-vilab/text-to-video-ms-1.7b", "priority": 1},
            {"model_id": "damo-vilab/text-to-video-ms-1.7b", "priority": 2},
            {"model_id": "cerspense/zeroscope_v2_576w", "priority": 3}
        ],
        "image-to-video": [
            {"model_id": "damo-vilab/modelscope-damo-img2vid", "priority": 1},
            {"model_id": "ali-vilab/modelscope-damo-img2vid", "priority": 2},
            {"model_id": "stabilityai/stable-video-diffusion-img2vid-xt", "priority": 3}
        ]
    }
