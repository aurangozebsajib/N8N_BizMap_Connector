
import os, json, gspread
from google.oauth2.service_account import Credentials
SCOPES=["https://www.googleapis.com/auth/spreadsheets"]
VIDEO_OUTPUTS_HEADERS=["video_label","segment_id","video_type","start_sec","end_sec","planned_duration_sec","clip_duration_sec","model_used","character_ref_image","output_file","status","dialect"]
AUDIO_OUTPUTS_HEADERS=["video_label","dialect","word_count","audio_duration_sec","mp3_file","catbox_link","status"]
def _load_sa():
    raw=os.environ.get("GOOGLE_SERVICE_JSON","")
    if not raw:
        raise RuntimeError("Missing env GOOGLE_SERVICE_JSON")
    try:
        info=json.loads(raw)
    except Exception as e:
        raise RuntimeError(f"GOOGLE_SERVICE_JSON invalid JSON: {e}")
    return info
def get_gspread_client():
    info=_load_sa()
    creds=Credentials.from_service_account_info(info, scopes=SCOPES)
    return gspread.authorize(creds)
def _open(client,sid):
    try:
        return client.open_by_key(sid)
    except Exception as e:
        raise RuntimeError(f"Failed to open sheet {sid}: {e}")
def _ensure_tab(ss,name,headers):
    try:
        ws=ss.worksheet(name)
    except gspread.WorksheetNotFound:
        ws=ss.add_worksheet(title=name, rows=1000, cols=max(20,len(headers)))
        ws.append_row(headers)
        print(f"Created tab {name}")
        return ws
    try:
        row1=ws.row_values(1)
    except:
        row1=[]
    if not row1:
        ws.update('A1',[headers])
        print(f"Init headers for {name}")
        return ws
    missing=[h for h in headers if h not in row1]
    if missing:
        ws.update('A1',[row1+missing])
        print(f"Added missing headers to {name}: {missing}")
    return ws
def _load_rows(ss,name):
    try:
        ws=ss.worksheet(name)
    except gspread.WorksheetNotFound:
        return None, []
    try:
        rec=ws.get_all_records()
    except Exception as e:
        print(f"Warning read {name}: {e}")
        rec=[]
    return ws, rec
def load_brain_keys():
    sid=os.environ.get("API_KEYS_SHEET","")
    if not sid:
        raise RuntimeError("Missing API_KEYS_SHEET")
    client=get_gspread_client()
    ss=_open(client,sid)
    ws,rows=_load_rows(ss,"API_Keys_Brain")
    if ws is None:
        raise RuntimeError("Tab API_Keys_Brain missing in API_KEYS_SHEET")
    active=[]
    for r in rows:
        if str(r.get("status","")).strip().lower()!="active":
            continue
        ak=str(r.get("api_key_value","")).strip()
        pv=str(r.get("provider","")).strip().lower()
        if not ak or not pv:
            continue
        active.append({"key_id":str(r.get("key_id","")).strip(),"api_key_value":ak,"provider":pv,"account_id":str(r.get("account_id","")).strip(),"model":str(r.get("model","")).strip()})
    if not active:
        raise RuntimeError("No active keys in tab API_Keys_Brain - add at least one row with status active")
    for k in active:
        print(f"::add-mask::{k['api_key_value']}")
    print(f"Loaded {len(active)} active brain keys")
    return active
def load_hf_keys():
    sid=os.environ.get("API_KEYS_SHEET","")
    client=get_gspread_client()
    ss=_open(client,sid)
    ws,rows=_load_rows(ss,"API_Keys_HF")
    if ws is None:
        raise RuntimeError("Tab API_Keys_HF missing in API_KEYS_SHEET")
    active=[]
    for r in rows:
        if str(r.get("status","")).strip().lower()!="active":
            continue
        ak=str(r.get("api_key_value","")).strip()
        if not ak:
            continue
        active.append({"key_id":str(r.get("key_id","")).strip(),"api_key_value":ak})
    if not active:
        raise RuntimeError("No active keys in tab API_Keys_HF")
    for k in active:
        print(f"::add-mask::{k['api_key_value']}")
    print(f"Loaded {len(active)} HF keys")
    return active
def load_model_routing():
    sid=os.environ.get("MODEL_STORAGE_SHEET","")
    if not sid:
        raise RuntimeError("Missing MODEL_STORAGE_SHEET")
    client=get_gspread_client()
    ss=_open(client,sid)
    ws,rows=_load_rows(ss,"Model_Routing")
    if ws is None:
        raise RuntimeError("Tab Model_Routing missing in MODEL_STORAGE_SHEET")
    if not rows:
        raise RuntimeError("Model_Routing tab empty")
    grouped={}
    for r in rows:
        task=str(r.get("task_type","")).strip().lower()
        mid=str(r.get("model_id","")).strip()
        if not task or not mid:
            continue
        try:
            pri=int(str(r.get("priority","")).strip() or "999")
        except:
            pri=999
        et=str(r.get("endpoint_type","")).strip().lower()
        if et and et!="inference-api":
            print(f"endpoint_type not supported yet: {et} for model {mid}, skipping row")
            continue
        grouped.setdefault(task,[]).append({"task_type":task,"model_id":mid,"priority":pri,"notes":str(r.get("notes","")),"endpoint_type":et})
    for t in grouped:
        grouped[t]=sorted(grouped[t], key=lambda x:x["priority"])
    if not grouped:
        raise RuntimeError("No valid rows in Model_Routing")
    print(f"Loaded routing counts: { {k:len(v) for k,v in grouped.items()} }")
    return grouped
def ensure_outputs_tabs():
    sid=os.environ.get("MODEL_STORAGE_SHEET","")
    client=get_gspread_client()
    ss=_open(client,sid)
    ws_v=_ensure_tab(ss,"Video_Outputs",VIDEO_OUTPUTS_HEADERS)
    ws_a=_ensure_tab(ss,"Audio_Outputs",AUDIO_OUTPUTS_HEADERS)
    return ws_v, ws_a
def append_row_by_headers(tab_name,row_dict):
    sid=os.environ.get("MODEL_STORAGE_SHEET","")
    client=get_gspread_client()
    ss=_open(client,sid)
    req=VIDEO_OUTPUTS_HEADERS if tab_name=="Video_Outputs" else AUDIO_OUTPUTS_HEADERS if tab_name=="Audio_Outputs" else list(row_dict.keys())
    ws=_ensure_tab(ss,tab_name,req)
    headers=ws.row_values(1)
    vals=[str(row_dict.get(h,"")) for h in headers]
    ws.append_row(vals, value_input_option="USER_ENTERED")
    print(f"Appended to {tab_name}")
