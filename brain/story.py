
import os, re, json, random
from datetime import datetime, timedelta, timezone
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
BD_TZ=timezone(timedelta(hours=6))
BANGLA_DIGITS=str.maketrans("০১২৩৪৫৬৭৮৯","0123456789")
HEADING_RE=re.compile(r"^Video\s*(\d+)\s*[|:\-–—,]\s*(\d{4})-(\d{1,2})-(\d{1,2})\s*$", re.IGNORECASE)
DIALECT_LINE_RE=re.compile(r"^\s*Dialect\s*:\s*(\S+)\s*$", re.IGNORECASE)
SCOPES=["https://www.googleapis.com/auth/documents.readonly"]
def _sa_creds():
    raw=os.environ.get("GOOGLE_SERVICE_JSON","")
    if not raw:
        raise RuntimeError("Missing GOOGLE_SERVICE_JSON")
    try:
        info=json.loads(raw)
    except Exception as e:
        raise RuntimeError(f"GOOGLE_SERVICE_JSON bad JSON: {e}")
    return Credentials.from_service_account_info(info, scopes=SCOPES)
def _extract_text_from_content(content_list):
    txt=[]
    for el in content_list or []:
        para=el.get("paragraph")
        if not para:
            continue
        for elem in para.get("elements",[]):
            tr=elem.get("textRun")
            if tr and "content" in tr:
                txt.append(tr["content"])
    return "".join(txt)
def _extract_from_tab_documenttab(doc_tab):
    body=doc_tab.get("body",{})
    return _extract_text_from_content(body.get("content",[]))
def _walk_tabs(tabs):
    full=""
    for tab in tabs or []:
        dtab=tab.get("documentTab")
        if dtab:
            full+=_extract_from_tab_documenttab(dtab)+"\n"
        childs=tab.get("childTabs",[])
        if childs:
            full+=_walk_tabs(childs)
    return full
def read_doc_text(doc_id):
    creds=_sa_creds()
    service=build("docs","v1",credentials=creds)
    try:
        doc=service.documents().get(documentId=doc_id, includeTabsContent=True).execute()
    except Exception as e:
        print(f"Failed to read Doc: status error {e}")
        raise
    if doc.get("tabs"):
        text=_walk_tabs(doc["tabs"])
        if text.strip():
            return text
    body=doc.get("body",{})
    text=_extract_text_from_content(body.get("content",[]))
    return text
def parse_entries(full_text):
    lines=full_text.splitlines()
    entries=[]
    current=None
    for orig_line in lines:
        stripped=orig_line.strip()
        if not stripped:
            if current is not None:
                current["lines"].append(orig_line)
            continue
        match_line=stripped.translate(BANGLA_DIGITS)
        m=HEADING_RE.match(match_line)
        if m:
            if current is not None:
                text_block="\n".join(current["lines"]).strip()
                if text_block:
                    current["text"]=text_block
                    entries.append(current)
                else:
                    print(f"Ignoring entry {current['label']} empty text")
            try:
                num=int(m.group(1))
                y=int(m.group(2)); mo=int(m.group(3)); d=int(m.group(4))
                datetime(y,mo,d)
                date_str=f"{y:04d}-{mo:02d}-{d:02d}"
                label=f"Video {num} | {date_str}"
                current={"number":num,"date_str":date_str,"year":y,"month":mo,"day":d,"label":label,"lines":[]}
            except Exception as e:
                print(f"Warning: invalid date in heading '{stripped}' -> {e}, ignoring")
                current=None
            continue
        if current is not None:
            current["lines"].append(orig_line)
    if current is not None:
        text_block="\n".join(current["lines"]).strip()
        if text_block:
            current["text"]=text_block
            entries.append(current)
    return entries
def select_entry(entries, target_date_str, video_number_str):
    if not target_date_str:
        now=datetime.now(BD_TZ).date()
        target_date_str=now.isoformat()
        print(f"VIDEO_DATE empty, using today BD {target_date_str}")
    try:
        datetime.strptime(target_date_str, "%Y-%m-%d")
    except:
        raise RuntimeError(f"Invalid VIDEO_DATE format {target_date_str}, expected YYYY-MM-DD")
    wanted_num=None
    if video_number_str and video_number_str.strip():
        try:
            wanted_num=int(video_number_str.strip())
        except:
            raise RuntimeError(f"Invalid VIDEO_NUMBER {video_number_str}")
    matches=[]
    for e in entries:
        if e["date_str"]==target_date_str:
            if wanted_num is not None and e["number"]!=wanted_num:
                continue
            matches.append(e)
    if not matches:
        found_dates=sorted(set([en["date_str"] for en in entries]))[:20]
        raise RuntimeError(f"No entry found for target date {target_date_str} number {video_number_str or 'any'}. Dates in doc (up to 20): {found_dates}")
    if len(matches)>1:
        print(f"Warning: {len(matches)} entries match {target_date_str} {video_number_str or ''}, using first {matches[0]['label']}, others: {[m['label'] for m in matches[1:]]}")
    chosen=matches[0]
    if len(chosen["text"])>12000:
        raise RuntimeError(f"Entry {chosen['label']} longer than 12000 chars ({len(chosen['text'])}), refusing to truncate")
    return chosen
def extract_dialect(text):
    dialect="none"
    cleaned_lines=[]
    found=False
    for line in text.splitlines():
        m=DIALECT_LINE_RE.match(line)
        if m and not found:
            val=m.group(1).strip().lower()
            dialect=val
            found=True
            continue
        cleaned_lines.append(line)
    cleaned="\n".join(cleaned_lines).strip()
    if not dialect or dialect=="none":
        return "none", cleaned
    if dialect=="auto":
        dialect=random.choice(["rangpuri","barishal","old-dhaka"])
        print(f"Dialect auto -> picked {dialect}")
        return dialect, cleaned
    if dialect not in ("rangpuri","barishal","old-dhaka","none"):
        print(f"Warning: unknown dialect '{dialect}' treated as none")
        return "none", cleaned
    return dialect, cleaned
def split_blocks(text, max_chars=1500):
    paras=text.split("\n")
    blocks=[]
    cur=""
    for p in paras:
        if cur and len(cur)+1+len(p) > max_chars:
            blocks.append(cur)
            cur=p
            while len(cur) > max_chars:
                sub=cur[:max_chars]
                last=-1
                for sep in ["।","?","!",".","\n"]:
                    idx=sub.rfind(sep)
                    if idx>last:
                        last=idx
                if last> max_chars*0.5:
                    blocks.append(cur[:last+1])
                    cur=cur[last+1:].lstrip()
                else:
                    blocks.append(cur[:max_chars])
                    cur=cur[max_chars:].lstrip()
        else:
            if cur:
                cur+="\n"+p
            else:
                cur=p
    if cur:
        blocks.append(cur)
    final=[]
    for b in blocks:
        if len(b)<=max_chars:
            final.append(b)
        else:
            for i in range(0,len(b),max_chars):
                final.append(b[i:i+max_chars])
    return final
def clean_for_tts(text):
    import re
    t=re.sub(r"[*#_`]+","",text)
    lines=[]
    for line in t.splitlines():
        l=re.sub(r"^\s*[-•]\s*","",line)
        lines.append(l)
    t="\n".join(lines)
    t=re.sub(r"[ \t]{2,}"," ",t)
    t=re.sub(r"\n{3,}","\n\n",t)
    latin=[]
    for ch in t:
        if ('A'<=ch<='Z' or 'a'<=ch<='z' or '0'<=ch<='9'):
            latin.append(ch)
            if len(latin)>=10:
                break
    if latin:
        print(f"Warning: Latin letters/digits remain in final script (owner writes numbers in Bangla). Sample: {''.join(latin[:20])}")
    return t.strip()
def apply_dialect_via_llm(full_text_with_dialect_line_removed, dialect, llm_pool):
    if dialect=="none":
        return full_text_with_dialect_line_removed
    import pathlib
    prompt_path=pathlib.Path(__file__).parent / "prompts" / "script_prompt.txt"
    template=prompt_path.read_text(encoding="utf-8")
    blocks=split_blocks(full_text_with_dialect_line_removed, max_chars=1500)
    converted=[]
    for idx, block in enumerate(blocks):
        case_text=f"Dialect: {dialect}\n{block}"
        prompt=template.replace("{CASE_TEXT}", case_text)
        try:
            out=llm_pool.call(prompt, preferred_providers=["gemini","openrouter","groq","nvidia","workers-ai"])
            out=out.strip()
            if not out:
                print(f"Dialect block {idx} empty, using original")
                converted.append(block)
                continue
            orig_len=len(block)
            conv_len=len(out)
            if conv_len < orig_len*0.8 or conv_len > orig_len*1.25:
                print(f"Warning: dialect block {idx} length guard fail orig {orig_len} conv {conv_len}, using original")
                converted.append(block)
            else:
                converted.append(out)
        except Exception as e:
            print(f"Dialect LLM failed block {idx}: {e}, using original")
            converted.append(block)
    final="\n\n".join(converted)
    return final
