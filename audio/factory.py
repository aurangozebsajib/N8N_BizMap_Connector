
import os, pathlib, json, time, re, requests
from gtts import gTTS
from pydub import AudioSegment
import gspread
from google.oauth2.service_account import Credentials
SCOPES=["https://www.googleapis.com/auth/spreadsheets"]
def _load_sa():
    raw=os.environ.get("GOOGLE_SERVICE_JSON","")
    if not raw:
        raise RuntimeError("Missing GOOGLE_SERVICE_JSON")
    try:
        info=json.loads(raw)
    except Exception as e:
        raise RuntimeError(f"GOOGLE_SERVICE_JSON bad JSON: {e}")
    return info
def get_gspread():
    info=_load_sa()
    creds=Credentials.from_service_account_info(info, scopes=SCOPES)
    return gspread.authorize(creds)
def ensure_and_append_audio(row_dict):
    sheet_id=os.environ.get("MODEL_STORAGE_SHEET","")
    if not sheet_id:
        print("No MODEL_STORAGE_SHEET, skipping sheet append")
        return
    client=get_gspread()
    try:
        ss=client.open_by_key(sheet_id)
    except Exception as e:
        print(f"Failed open sheet {e}")
        return
    headers=["video_label","dialect","word_count","audio_duration_sec","mp3_file","catbox_link","status"]
    try:
        ws=ss.worksheet("Audio_Outputs")
    except gspread.WorksheetNotFound:
        ws=ss.add_worksheet(title="Audio_Outputs", rows=1000, cols=20)
        ws.append_row(headers)
    try:
        row1=ws.row_values(1)
    except:
        row1=[]
    if not row1:
        ws.update('A1',[headers])
        row1=headers
    missing=[h for h in headers if h not in row1]
    if missing:
        ws.update('A1',[row1+missing])
        row1=row1+missing
    vals=[str(row_dict.get(h,"")) for h in row1]
    try:
        ws.append_row(vals, value_input_option="USER_ENTERED")
        print("Appended Audio_Outputs")
    except Exception as e:
        print(f"Append Audio_Outputs failed: {e}")
def safe_label_filename(label):
    s=re.sub(r'[\\/:*?"<>|]+','_', label)
    s=s.replace(" ","_").replace("|","_")
    s=re.sub(r'[^\w\-\u0980-\u09FF]', '_', s, flags=re.UNICODE)
    s=re.sub(r'_+','_', s)
    if len(s)>80:
        s=s[:80]
    return s or "audio"
def split_for_tts(text, max_chars=400):
    import re
    sentences=re.split(r'([।\?\!\.]+)', text)
    sents=[]
    for i in range(0,len(sentences),2):
        s=sentences[i].strip()
        d=sentences[i+1] if i+1 < len(sentences) else ""
        if not s:
            continue
        sents.append(s+d)
    chunks=[]
    cur=""
    for sent in sents:
        if not cur:
            cur=sent
        elif len(cur)+1+len(sent) <= max_chars:
            cur=cur+" "+sent
        else:
            chunks.append(cur)
            cur=sent
            while len(cur) > max_chars:
                chunks.append(cur[:max_chars])
                cur=cur[max_chars:]
    if cur:
        chunks.append(cur)
    return chunks
def tts_piece(text, tmp_path):
    for attempt in range(3):
        try:
            tts=gTTS(text=text, lang="bn", slow=False)
            tts.save(tmp_path)
            return True
        except Exception as e:
            print(f"gTTS attempt {attempt+1} failed: {e}")
            wait=[2,5][attempt] if attempt<2 else 0
            if wait:
                time.sleep(wait)
    return False
def upload_catbox(file_path):
    try:
        with open(file_path,"rb") as f:
            r=requests.post("https://catbox.moe/user/api.php", data={"reqtype":"fileupload"}, files={"fileToUpload": f}, timeout=60)
        if r.status_code==200 and r.text.startswith("http"):
            print(f"Catbox uploaded {r.text[:100]}")
            return r.text.strip()
        else:
            print(f"Catbox failed status {r.status_code} text {r.text[:200]}")
            return ""
    except Exception as e:
        print(f"Catbox exception {e}")
        return ""
def main():
    plan_path=None
    for c in [pathlib.Path("output/plan.json"), pathlib.Path("plan.json")]:
        if c.exists():
            plan_path=c
            break
    if plan_path is None:
        raise RuntimeError("plan.json missing, audio job reads only plan artifact")
    with open(plan_path,"r",encoding="utf-8") as f:
        plan=json.load(f)
    master=plan.get("master_script_bn","").strip()
    if not master:
        raise RuntimeError("master_script_bn empty in plan")
    video_label=plan.get("video_label","Video")
    dialect=plan.get("dialect_used","none")
    word_count=len(master.split())
    pieces=split_for_tts(master, max_chars=400)
    print(f"TTS split into {len(pieces)} pieces")
    out_dir=pathlib.Path("output/audio")
    out_dir.mkdir(parents=True, exist_ok=True)
    safe_name=safe_label_filename(video_label)
    mp3_path=out_dir / f"{safe_name}.mp3"
    temp_files=[]
    combined=AudioSegment.empty()
    for idx, piece in enumerate(pieces):
        tmp_mp3=out_dir / f"_tmp_{idx}.mp3"
        ok=tts_piece(piece, str(tmp_mp3))
        if not ok:
            for tf in temp_files:
                try: os.remove(tf)
                except: pass
            raise RuntimeError(f"gTTS failed for piece {idx} after 3 tries")
        temp_files.append(str(tmp_mp3))
        try:
            seg=AudioSegment.from_file(str(tmp_mp3))
            combined+=seg
        except Exception as e:
            try:
                seg=AudioSegment.from_mp3(str(tmp_mp3))
                combined+=seg
            except Exception as e2:
                raise RuntimeError(f"Audio segment load failed {idx}: {e2}")
    combined.export(str(mp3_path), format="mp3")
    print(f"Exported {mp3_path} duration {len(combined)/1000.0}s")
    for tf in temp_files:
        try: os.remove(tf)
        except: pass
    duration_sec=len(combined)/1000.0
    meta_path=out_dir / "audio_meta.json"
    meta={"video_label": video_label,"audio_duration_sec": round(duration_sec,2),"word_count": word_count}
    with open(meta_path,"w",encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    upload_flag=os.environ.get("UPLOAD_CATBOX","false").lower()
    catbox_link=""
    if upload_flag=="true":
        catbox_link=upload_catbox(str(mp3_path))
    else:
        print("UPLOAD_CATBOX not true, skipping catbox")
    row={"video_label": video_label,"dialect": dialect,"word_count": word_count,"audio_duration_sec": round(duration_sec,2),"mp3_file": f"{safe_name}.mp3","catbox_link": catbox_link,"status": "success"}
    try:
        ensure_and_append_audio(row)
    except Exception as e:
        print(f"Sheet append warning: {e}")
if __name__=="__main__":
    try:
        main()
    except Exception as e:
        print(f"Audio job failed: {e}")
        try:
            import pathlib as pl
            label="unknown"
            for cand in [pl.Path("output/plan.json"), pl.Path("plan.json")]:
                if cand.exists():
                    with open(cand,"r",encoding="utf-8") as f:
                        j=json.load(f)
                        label=j.get("video_label","unknown")
                    break
            ensure_and_append_audio({"video_label": label,"dialect": "","word_count": "","audio_duration_sec": "","mp3_file": "","catbox_link": "","status": f"failed: {str(e)[:200]}"})
        except Exception as e2:
            print(f"Failed to log failure to sheet: {e2}")
        raise
