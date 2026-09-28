
import os, re, json, math
import brain.config as cfg
LESSON_STARTS=("প্রথম শিক্ষা","দ্বিতীয় শিক্ষা","তৃতীয় শিক্ষা","সারকথা")
def _words(text):
    return len(text.split())
def split_into_chunks(final_script, max_segments):
    paras=[p.strip() for p in final_script.split("\n") if p.strip()]
    sentences=[]
    sep_re=re.compile(r"([।\?\!\.]+)")
    for para in paras:
        is_lesson=False
        for ls in LESSON_STARTS:
            if para.startswith(ls):
                is_lesson=True
                break
        if is_lesson:
            sentences.append(para)
            continue
        parts=sep_re.split(para)
        for i in range(0,len(parts),2):
            s=parts[i].strip()
            delim=parts[i+1] if i+1 < len(parts) else ""
            if not s:
                continue
            sentences.append(s+delim)
    chunks=[]
    cur_chunk=""
    cur_words=0
    for sent in sentences:
        is_lesson=any(sent.startswith(ls) for ls in LESSON_STARTS)
        if is_lesson:
            if cur_chunk:
                chunks.append(cur_chunk.strip())
                cur_chunk=""
                cur_words=0
            chunks.append(sent.strip())
            continue
        w=_words(sent)
        if cur_words + w <= cfg.MAX_SEGMENT_WORDS:
            cur_chunk = (cur_chunk+" "+sent).strip() if cur_chunk else sent
            cur_words+=w
        else:
            if cur_chunk:
                chunks.append(cur_chunk.strip())
            cur_chunk=sent
            cur_words=w
    if cur_chunk:
        chunks.append(cur_chunk.strip())
    total_words=_words(final_script)
    desired=int(round(total_words / cfg.AVG_WORDS_PER_SEGMENT))
    desired=max(3, desired)
    desired=min(desired, max_segments)
    while len(chunks) > desired:
        min_idx=0
        min_len=_words(chunks[0])+_words(chunks[1]) if len(chunks)>1 else 9999
        for i in range(len(chunks)-1):
            l=_words(chunks[i])+_words(chunks[i+1])
            if l < min_len:
                min_len=l
                min_idx=i
        chunks[min_idx]=chunks[min_idx]+" "+chunks[min_idx+1]
        del chunks[min_idx+1]
    while len(chunks) < desired:
        longest_idx=max(range(len(chunks)), key=lambda i: _words(chunks[i]))
        txt=chunks[longest_idx]
        ws=txt.split()
        if len(ws) <= cfg.MIN_SEGMENT_WORDS:
            break
        mid=len(ws)//2
        left=" ".join(ws[:mid])
        right=" ".join(ws[mid:])
        chunks[longest_idx]=left
        chunks.insert(longest_idx+1, right)
    return chunks
def build_segmentation_prompt(chunks):
    import pathlib
    tmpl_path=pathlib.Path(__file__).parent / "prompts" / "segmentation_prompt.txt"
    tmpl=tmpl_path.read_text(encoding="utf-8")
    chunks_text=""
    for i,ch in enumerate(chunks, start=1):
        chunks_text+=f"{i}. {ch}\n"
    return tmpl.replace("{CHUNKS_TEXT}", chunks_text), chunks
def parse_llm_json(text):
    t=text.strip()
    if t.startswith("```"):
        t=re.sub(r"^```.*\n","",t)
        t=re.sub(r"\n```$","",t)
    first=t.find("{")
    last=t.rfind("}")
    if first==-1 or last==-1:
        raise ValueError("No JSON braces found")
    j_str=t[first:last+1]
    return json.loads(j_str)
def validate_segments(parsed, chunks):
    segs=parsed.get("segments",[])
    if len(segs)!=len(chunks):
        raise ValueError(f"segment count mismatch got {len(segs)} expected {len(chunks)}")
    for i, s in enumerate(segs):
        if s.get("chunk") != i+1:
            if s.get("chunk") is None:
                raise ValueError("chunk id missing")
    valid={"text-to-video","image-to-video","text-animation"}
    for s in segs:
        vt=str(s.get("video_type","")).strip().lower()
        if vt not in valid:
            raise ValueError(f"invalid video_type {vt}")
    return segs
def fallback_segments(chunks):
    res=[]
    style="clean semi-realistic 2D illustration, soft lighting, warm colors"
    for i,ch in enumerate(chunks, start=1):
        has_num=bool(re.search(r"\d", ch))
        is_lesson=any(ch.startswith(ls) for ls in LESSON_STARTS)
        if is_lesson or has_num:
            vt="text-animation"
        elif i==1:
            vt="image-to-video"
        else:
            vt="text-to-video"
        res.append({"chunk": i,"video_type": vt,"visual_prompt": "cinematic illustration of the scene, detailed background","style_notes": style,"sound_design": {"music_mood":"calm","sfx":[]}})
    return res
def compute_timing(chunks):
    segments=[]
    total=0.0
    total_words=0
    for i,ch in enumerate(chunks, start=1):
        wc=len(ch.split())
        dur=max(cfg.MIN_PLANNED_DURATION_SEC, wc / cfg.WORDS_PER_SECOND)
        start=total
        end=start+dur
        total=end
        total_words+=wc
        segments.append({"segment_id": i,"text_portion": ch,"word_count": wc,"start_sec": round(start,2),"end_sec": round(end,2),"planned_duration_sec": round(dur,2)})
    return segments, total, total_words
def run_segmentation(final_script, llm_pool, max_segments):
    chunks=split_into_chunks(final_script, max_segments)
    print(f"Split into {len(chunks)} chunks, total words {len(final_script.split())}")
    prompt,_ = build_segmentation_prompt(chunks)
    last_err=None
    for attempt in range(3):
        try:
            raw=llm_pool.call(prompt, preferred_providers=["gemini","groq","openrouter","nvidia","workers-ai"])
            parsed=parse_llm_json(raw)
            segs=validate_segments(parsed, chunks)
            print(f"Segmentation LLM succeeded attempt {attempt+1}")
            timed, total, total_words = compute_timing(chunks)
            base_style=segs[0].get("style_notes","clean semi-realistic 2D illustration, soft lighting, warm colors")
            merged=[]
            for t, l in zip(timed, segs):
                merged.append({**t, "video_type": l["video_type"], "visual_prompt": l.get("visual_prompt","cinematic illustration"), "style_notes": base_style, "sound_design": l.get("sound_design",{"music_mood":"calm","sfx":[]})})
            if len(merged)>=3 and not any(s["video_type"]=="image-to-video" for s in merged):
                merged[0]["video_type"]="image-to-video"
                print("Enforced first segment image-to-video")
            return merged, total, total_words
        except Exception as e:
            print(f"Segmentation attempt {attempt+1} failed: {e}")
            last_err=e
            continue
    print(f"All segmentation LLM attempts failed ({last_err}), using fallback")
    fb=fallback_segments(chunks)
    timed, total, total_words = compute_timing(chunks)
    merged=[]
    base_style=fb[0]["style_notes"]
    for t,l in zip(timed, fb):
        merged.append({**t, "video_type": l["video_type"], "visual_prompt": l["visual_prompt"], "style_notes": base_style, "sound_design": l["sound_design"]})
    return merged, total, total_words
