import os
import re
import json
import pathlib
from datetime import datetime, timezone, timedelta
import brain.config as cfg

LESSON_STARTS = ("প্রথম শিক্ষা", "দ্বিতীয় শিক্ষা", "তৃতীয় শিক্ষা", "সারকথা")
BANGLA_DIGITS = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")

def _words(text):
    return len(text.strip().split())

def split_into_chunks(final_script, max_segments=10):
    paras = [p.strip() for p in final_script.split("\n") if p.strip()]
    sentences = []
    sep_re = re.compile(r"([।\?\!\.]+)")
    for para in paras:
        is_lesson = any(para.startswith(ls) for ls in LESSON_STARTS)
        if is_lesson:
            sentences.append(para)
            continue
        parts = sep_re.split(para)
        for i in range(0, len(parts), 2):
            s = parts[i].strip()
            delim = parts[i + 1] if i + 1 < len(parts) else ""
            if not s:
                continue
            sentences.append(s + delim)

    chunks = []
    cur_chunk = ""
    cur_words = 0
    for sent in sentences:
        is_lesson = any(sent.startswith(ls) for ls in LESSON_STARTS)
        if is_lesson:
            if cur_chunk:
                chunks.append(cur_chunk.strip())
                cur_chunk = ""
                cur_words = 0
            chunks.append(sent.strip())
            continue
        w = _words(sent)
        if cur_words + w <= cfg.MAX_SEGMENT_WORDS:
            cur_chunk = (cur_chunk + " " + sent).strip() if cur_chunk else sent
            cur_words += w
        else:
            if cur_chunk:
                chunks.append(cur_chunk.strip())
            cur_chunk = sent
            cur_words = w
    if cur_chunk:
        chunks.append(cur_chunk.strip())

    total_words = _words(final_script)
    desired = int(round(total_words / cfg.AVG_WORDS_PER_SEGMENT))
    desired = max(3, desired)
    desired = min(desired, max_segments)

    while len(chunks) > desired and len(chunks) > 2:
        min_idx = 0
        min_len = 9999
        for i in range(len(chunks) - 1):
            if any(chunks[i].startswith(ls) for ls in LESSON_STARTS) or any(chunks[i+1].startswith(ls) for ls in LESSON_STARTS):
                continue
            l = _words(chunks[i]) + _words(chunks[i + 1])
            if l < min_len:
                min_len = l
                min_idx = i
        if min_len == 9999:
            break
        chunks[min_idx] = chunks[min_idx] + " " + chunks[min_idx + 1]
        del chunks[min_idx + 1]

    return chunks

def apply_dialect(text, dialect):
    if not dialect or dialect in ("none", "standard"):
        return text
    if dialect == "auto":
        import random
        dialect = random.choice(["rangpuri", "barishal", "old-dhaka"])

    lines = text.split("\n")
    out = []
    for line in lines:
        if any(line.strip().startswith(ls) for ls in LESSON_STARTS):
            out.append(line)
            continue
        l = line
        if dialect == "rangpuri":
            l = re.sub(r'\bআমি\b', 'মুই', l)
            l = re.sub(r'\bআমার\b', 'হামার', l)
            l = re.sub(r'\bআমরা\b', 'হামরা', l)
            l = re.sub(r'\bকোথায়\b', 'কোটেই', l)
        elif dialect == "barishal":
            l = re.sub(r'\bযাব\b', 'যামু', l)
            l = re.sub(r'\bখাব\b', 'খামু', l)
            l = re.sub(r'\bকরব\b', 'করমু', l)
            l = re.sub(r'\bবলেছি\b', 'কইছি', l)
            l = re.sub(r'\bকেন\b', 'ক্যান', l)
        elif dialect == "old-dhaka":
            l = re.sub(r'\bএটা\b', 'এইডা', l)
            l = re.sub(r'\bসেটা\b', 'হেইডা', l)
            l = re.sub(r'\bসে\b', 'হেয়', l)
            l = re.sub(r'\bএকটু\b', 'ইট্টু', l)
            l = re.sub(r'\bহয়েছে\b', 'হইছে', l)
        out.append(l)
    return "\n".join(out)

def generate_character_design(context_text, mode="per_video"):
    if mode == "fixed":
        return {
            "mode": "fixed",
            "name": "সজীব ভাই (BizMap Host)",
            "description": "A 28-year-old friendly Bangladeshi host in modern navy blue kurta with specs, plain studio backdrop, clean 2D illustration style.",
            "age_range": "26-30 years",
            "gender": "Male",
            "clothing": "Contemporary navy kurta",
            "colors": "Navy blue, ivory, gold",
            "style": "Clean semi-realistic 2D illustration"
        }
    if "তাঁতি" in context_text or "গ্রাম" in context_text:
        return {
            "mode": "per_video",
            "name": "রফিক মিয়া (Master Craftsman)",
            "description": "A 45-year-old resilient Bangladeshi artisan in grey traditional cotton panjabi with folded sleeves, clean neutral minimalist workshop background.",
            "age_range": "42-48 years",
            "gender": "Male",
            "clothing": "Traditional woven panjabi",
            "colors": "Earthy grey, terracotta",
            "style": "Clean semi-realistic 2D illustration"
        }
    return {
        "mode": "per_video",
        "name": "তারেক রহমান (Modern Entrepreneur)",
        "description": "A 29-year-old confident Bengali entrepreneur in a teal shirt with smartphone, clean background, modern rim lighting.",
        "age_range": "27-32 years",
        "gender": "Male",
        "clothing": "Teal smart-casual linen shirt",
        "colors": "Teal, warm copper",
        "style": "Clean semi-realistic 2D illustration"
    }

def run_plan():
    """
    Main Plan Runner
    Reads story, handles dialect, designs character, splits into segments,
    and writes output/plan.json and output/narration.txt.
    """
    print("=== Running Brain Planner ===")
    
    # 1. Load target parameters
    target_date = os.environ.get(cfg.VIDEO_DATE_ENV, "")
    target_num = os.environ.get(cfg.VIDEO_NUMBER_ENV, "")
    char_mode = os.environ.get(cfg.CHARACTER_MODE_ENV, "per_video")
    max_segments = int(os.environ.get(cfg.MAX_SEGMENTS_ENV, "10"))
    
    # 2. Get script content
    raw_script = ""
    dialect = "auto"
    doc_id = os.environ.get(cfg.STORY_STORAGE_DOC, "")
    
    if doc_id and os.environ.get(cfg.GOOGLE_SERVICE_JSON):
        try:
            from brain.story import read_doc_text, parse_entries, select_entry
            print(f"Reading Google Doc: {doc_id}...")
            full_text = read_doc_text(doc_id)
            entries = parse_entries(full_text)
            selected = select_entry(entries, target_date, target_num)
            if selected:
                raw_script = selected.get("text", "")
                print(f"Loaded entry: {selected.get('label')}")
        except Exception as e:
            print(f"Warning: Could not read Google Doc ({e}), using fallback story.")
            
    if not raw_script.strip():
        # Check local files or use default sample story
        if os.path.exists("story.txt"):
            with open("story.txt", "r", encoding="utf-8") as f:
                raw_script = f.read()
        elif os.path.exists("input/story.txt"):
            with open("input/story.txt", "r", encoding="utf-8") as f:
                raw_script = f.read()
        else:
            raw_script = """Video 1 | 2026-10-02
Dialect: rangpuri
রংপুরের গংগাচড়ার তাঁতি রফিক মিয়া বিশ বছর ধরে ঐতিহ্যবাহী শতরঞ্জি তৈরি করছেন। আগে স্থানীয় হাটে খুব কম দামে বিক্রি করতে হতো।
রফিক বললেন, "হামার এই কষ্টের দাম শহরে কেউ দিতে চায় না বাহে। মুই কি আর করমু, দিনরাত পরিশ্রম করেও সংসারের খরচ ওঠে না।"
এরপর রফিকের ছেলে BizMap এর মাধ্যমে তাদের পণ্যের ফেসবুক পেজ এবং গুগল ম্যাপ লিস্টিং তৈরি করে দেয়।
প্রথম সপ্তাহেই ঢাকা ও চট্টগ্রাম থেকে সরাসরি পাইকারি অর্ডারের ফোন আসতে শুরু করে।
প্রথম শিক্ষা: সনাতন পণ্যকে ডিজিটাল প্ল্যাটফর্মে আনলে মধ্যস্বত্বভোগী ছাড়াই ন্যায্য মূল্য পাওয়া যায়।
দ্বিতীয় শিক্ষা: সঠিক কন্টেন্ট এবং ভিডিওর মাধ্যমে পণ্যের সততা ফুটিয়ে তুললে ক্রেতার আস্থা দ্রুত বাড়ে।
সারকথা: ঐতিহ্যের সাথে আধুনিক প্রযুক্তির মেলবন্ধনই গ্রামীণ ব্যবসার নতুন দিগন্ত খুলে দেয়।"""

    # Parse dialect line if in script
    lines = raw_script.splitlines()
    body_lines = []
    video_label = "Video 1 | 2026-10-02"
    for line in lines:
        if line.strip().lower().startswith("dialect:"):
            dialect = line.strip().split(":", 1)[1].strip().lower()
            continue
        if line.strip().lower().startswith("video"):
            video_label = line.strip()
            continue
        body_lines.append(line)
        
    script_body = "\n".join(body_lines).strip()
    
    # 3. Apply Dialect
    final_script = apply_dialect(script_body, dialect)
    
    # 4. Split into chunks
    chunks = split_into_chunks(final_script, max_segments=max_segments)
    
    # 5. Design Character
    character = generate_character_design(final_script, mode=char_mode)
    
    # 6. Build Segments
    segments = []
    WORDS_PER_SEC = 2.5
    for i, ch in enumerate(chunks, start=1):
        w = _words(ch)
        planned_dur = max(3.0, round(w / WORDS_PER_SEC, 1))
        is_lesson = any(ch.startswith(ls) for ls in LESSON_STARTS)
        
        if is_lesson:
            vtype = "text-animation"
            visual_prompt = f"Kinetic typography in bold golden Bengali lettering on dark clean slate backdrop, highlighting key takeaway: {ch[:50]}"
            music_mood = "Uplifting crescendo acoustic folk melody"
            sfx = ["bell chime", "whoosh transition"]
        elif i == 1:
            vtype = "image-to-video"
            visual_prompt = f"{character['description']} Centered portrait looking at camera with subtle breathing motion."
            music_mood = "Warm acoustic dotara and light tabla"
            sfx = ["subtle breeze"]
        else:
            vtype = "text-to-video"
            visual_prompt = f"Vibrant South Asian commerce scene, artisan workshop, handloom products, authentic lighting."
            music_mood = "Energetic entrepreneurial rhythm"
            sfx = ["ambient chatter", "packaging sound"]
            
        segments.append({
            "segment_id": i,
            "chunk": i,
            "text_portion": ch,
            "word_count": w,
            "planned_duration_sec": planned_dur,
            "video_type": vtype,
            "visual_prompt": visual_prompt,
            "style_notes": "clean semi-realistic 2D illustration, soft lighting, warm colors",
            "sound_design": {
                "music_mood": music_mood,
                "sfx": sfx
            }
        })
        
    plan = {
        "video_label": video_label,
        "dialect_used": dialect,
        "character": character,
        "master_script_bn": final_script,
        "total_words": sum(s["word_count"] for s in segments),
        "total_duration_sec": round(sum(s["planned_duration_sec"] for s in segments), 1),
        "segments": segments,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    # Write outputs
    for p in ["output", "output/plan", "brain/output"]:
        pathlib.Path(p).mkdir(parents=True, exist_ok=True)
        
    plan_out_1 = pathlib.Path("output/plan.json")
    plan_out_2 = pathlib.Path("output/plan/plan.json")
    narration_out = pathlib.Path("output/narration.txt")
    
    with open(plan_out_1, "w", encoding="utf-8") as f:
        json.dump(plan, f, ensure_ascii=False, indent=2)
    with open(plan_out_2, "w", encoding="utf-8") as f:
        json.dump(plan, f, ensure_ascii=False, indent=2)
    with open(narration_out, "w", encoding="utf-8") as f:
        f.write(final_script)
        
    print(f"✅ Successfully generated plan: {plan_out_1} ({len(segments)} segments, {plan['total_duration_sec']}s)")
    return 0

if __name__ == "__main__":
    run_plan()
