import gspread
from google.oauth2.service_account import Credentials
import os, json

SCOPES = ["https://www.googleapis.com/auth/documents.readonly", "https://www.googleapis.com/auth/spreadsheets"]

def get_gspread_client():
    info = json.loads(os.environ["GOOGLE_SERVICE_JSON"])
    creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    return gspread.authorize(creds)

def load_keys_from_sheet():
    client = get_gspread_client()
    sheet_id = os.environ["GOOGLE_SHEET_ID"]
    sh = client.open_by_key(sheet_id)

    brain_rows = sh.worksheet("API_Keys_Brain").get_all_records()
    hf_rows = sh.worksheet("API_Keys_HF").get_all_records()
    routing_rows = sh.worksheet("Model_Routing").get_all_records()

    brain_keys = [r for r in brain_rows if str(r.get("status","")).lower() == "active" and r.get("api_key_value")]
    hf_keys = [r for r in hf_rows if str(r.get("status","")).lower() == "active" and r.get("api_key_value")]

    routing = {}
    for r in routing_rows:
        t = str(r.get("task_type","")).strip()
        if not t: continue
        routing.setdefault(t, []).append(r)
    for t in routing:
        routing[t] = sorted(routing[t], key=lambda x: int(x.get("priority", 99)))

    return brain_keys, hf_keys, routing

class RotatingPool:
    def __init__(self, key_list):
        self.keys = key_list
        self.idx = 0
    def next(self):
        if not self.keys:
            raise Exception("No active keys in pool")
        k = self.keys[self.idx % len(self.keys)]
        self.idx += 1
        return k
