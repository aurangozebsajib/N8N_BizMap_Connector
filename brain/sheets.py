import os
import gspread
from google.oauth2.service_account import Credentials

def load_brain_keys():
    """Load API keys from the external Google Sheet without strict status checks."""
    # Secrets বা Environment থেকে শিট আইডি নেওয়া
    sheet_id = os.environ.get("API_KEYS_SHEET")
    if not sheet_id:
        # ফলব্যাক বা লোকাল টেস্টের জন্য
        raise RuntimeError("Missing API_KEYS_SHEET environment variable")
    
    # গাণিতিক বা গুগল শিট অথেন্টিকেশন ও লোডিং
    # (আপনার প্রজেক্টের অরিজিনাল ক্রেডেনশিয়াল হ্যান্ডলিং বজায় রেখে শুধু স্ট্যাটাস চেক বাইপাস করা হলো)
    from brain.utils import get_gspread_client
    client = get_gspread_client()
    sheet = client.open_by_key(sheet_id)
    
    # 'Brain API ' বা 'API_Keys_Brain' ট্যাব থেকে ডেটা নেওয়া
    try:
        worksheet = sheet.worksheet("Brain API ")
    except:
        worksheet = sheet.worksheet("API_Keys_Brain")
        
    records = worksheet.get_all_records()
    
    # স্ট্যাটাস চেক ছাড়াই সরাসরি সব রেকর্ড রিটার্ন করা
    keys = []
    for row in records:
        # কলামের নাম যাই হোক না কেন, এপিআই কি এক্সট্রাক্ট করে নেওয়া
        key_val = row.get("API Keys") or row.get("API keys") or list(row.values())[-1]
        model_name = row.get("Model Name") or "Openrouter"
        if key_val:
            keys.append({"model": model_name, "key": key_val})
            
    return keys
