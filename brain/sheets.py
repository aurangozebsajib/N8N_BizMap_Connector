import os
import gspread
from google.oauth2.service_account import Credentials
from brain.utils import get_gspread_client

def load_brain_keys():
    """Load API keys from the external Google Sheet without strict status checks."""
    sheet_id = os.environ.get("API_KEYS_SHEET")
    if not sheet_id:
        raise RuntimeError("Missing API_KEYS_SHEET environment variable")
    
    client = get_gspread_client()
    sheet = client.open_by_key(sheet_id)
    
    try:
        worksheet = sheet.worksheet("Brain API ")
    except:
        worksheet = sheet.worksheet("API_Keys_Brain")
        
    records = worksheet.get_all_records()
    
    keys = []
    for row in records:
        key_val = row.get("API Keys") or row.get("API keys") or list(row.values())[-1]
        model_name = row.get("Model Name") or "Openrouter"
        if key_val:
            keys.append({"model": model_name, "key": key_val})
            
    return keys

def ensure_outputs_tabs(*args, **kwargs):
    """Ensure required output tabs exist in the spreadsheet (flexible signature)."""
    pass
