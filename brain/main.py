import os, json, re
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from api_pool import load_keys_from_sheet, RotatingPool
from text_engine import extract_case, call_brain_llm_with_pool
from character_engine import design_character, generate_reference_image
from video_engine import generate_segment
import gspread

SCOPES = ["https://www.googleapis.com/auth/documents.readonly", "https://www.googleapis.com/auth/spreadsheets"]

def read_google_doc(doc_id):
    info = json.loads(os.environ["GOOGLE_SERVICE_JSON"])
    creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    service = build('docs', 'v1', credentials=creds)
    doc = service.documents().get(documentId=doc_id).execute()
    text = ""
    for c in doc.get("body",{}).get("content",[]):
        if "paragraph" in c:
            for e in c["paragraph"].get("elements",[]):
                if "textRun" in e:
                    text += e["textRun"]["content"]
    return text

def main():
    print("Loading keys from Google Sheet...")
    brain_keys, hf_keys, routing = load_keys_from_sheet()
    brain_pool = RotatingPool(brain_keys)
    hf_pool = RotatingPool(hf_keys)
    print(f"Loaded {len(brain_keys)} brain keys, {len(hf_keys)} HF keys")

    doc_text = read_google_doc(os.environ["GOOGLE_DOC_ID"])
    case_idx = int(os.environ.get("CASE_INDEX","0"))
    case_id, case_text = extract_case(doc_text, target_index=case_idx)
    print(f"Selected {case_id}")

    with open("brain/prompts/script_prompt.txt", encoding="utf-8") as f:
        script_prompt = f.read().replace("{CASE_TEXT}", case_text[:6000])
    master_script = call_brain_llm_with_pool(brain_pool, script_prompt)
    print(f"Master script length: {len(master_script)}")

    with open("brain/prompts/segmentation_prompt.txt", encoding="utf-8") as f:
        seg_prompt = f.read().replace("{MASTER_SCRIPT}", master_script).replace("{CASE_ID}", case_id)
    seg_json_str = call_brain_llm_with_pool(brain_pool, seg_prompt)
    seg_json_str = re.sub(r"```json|```", "", seg_json_str).strip()
    data = json.loads(seg_json_str)

    with open("brain/prompts/character_prompt.txt", encoding="utf-8") as f:
        char_prompt = f.read()
    char_desc = design_character(brain_pool, case_text, char_prompt)
    print(f"Character: {char_desc}")

    ref_path, ref_model, _ = generate_reference_image(hf_pool, routing, char_desc)
    print(f"Ref image: {ref_path} via {ref_model}")

    info = json.loads(os.environ["GOOGLE_SERVICE_JSON"])
    creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(os.environ["GOOGLE_SHEET_ID"]).worksheet("Video_Outputs")

    for seg in data["segments"]:
        out_path, model_used, status = generate_segment(hf_pool, routing, seg, ref_path, char_desc)
        row = [case_id, seg["segment_id"], seg["video_type"], model_used or "", ref_path, out_path or "", status]
        try:
            sheet.append_row(row)
        except Exception as e:
            print(f"Sheet log failed: {e}")
        print(f"Done segment {seg['segment_id']}: {status}")

    print("Pipeline finished")

if __name__ == "__main__":
    main()
