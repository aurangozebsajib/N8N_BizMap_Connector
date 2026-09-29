
import argparse, os, json, pathlib
import brain.config as cfg
def run_plan():
    from brain.story import read_doc_text, parse_entries, select_entry, extract_dialect, apply_dialect_via_llm, clean_for_tts
    from brain.planner import run_segmentation
    from brain.character import get_character
    from brain.llm_pool import create_pool
    # try:
    # from brain.sheets import ensure_outputs_tabs
        pass
    doc_id=os.environ.get(cfg.STORY_STORAGE_DOC,"")
    if not doc_id:
        raise RuntimeError("Missing STORY_STORAGE_DOC")
    video_date=os.environ.get(cfg.VIDEO_DATE_ENV,"")
    video_number=os.environ.get(cfg.VIDEO_NUMBER_ENV,"")
    char_mode=os.environ.get(cfg.CHARACTER_MODE_ENV,"per_video")
    max_seg_env=os.environ.get(cfg.MAX_SEGMENTS_ENV,"10")
    try:
        max_seg=int(max_seg_env)
    except:
        max_seg=cfg.DEFAULT_MAX_SEGMENTS
    print(f"Reading Doc {doc_id[:10]}... (not logging full ID)")
    full_text=read_doc_text(doc_id)
    if not full_text.strip():
        raise RuntimeError("Story Doc empty")
    entries=parse_entries(full_text)
    print(f"Found {len(entries)} entries in Doc")
    chosen=select_entry(entries, video_date.strip() if video_date else "", video_number.strip() if video_number else "")
    print(f"Selected {chosen['label']} with {len(chosen['text'])} chars")
    dialect, cleaned = extract_dialect(chosen["text"])
    print(f"Detected dialect line -> {dialect}")
    llm_pool=create_pool()
    if dialect=="none":
        final_script=cleaned
        dialect_used="none"
    else:
        final_script=apply_dialect_via_llm(cleaned, dialect, llm_pool)
        dialect_used=dialect
    master_bn=clean_for_tts(final_script)
    if not master_bn.strip():
        raise RuntimeError("Final script empty after cleaning")
    segments, total_sec, total_words = run_segmentation(master_bn, llm_pool, max_seg)
    char_info=get_character(char_mode, master_bn, llm_pool)
    video_label=chosen["label"]
    video_date_norm=chosen["date_str"]
    plan={"video_label": video_label,"video_date": video_date_norm,"dialect_used": dialect_used,"master_script_bn": master_bn,"word_count": total_words,"estimated_total_sec": round(total_sec,2),"character": char_info,"segments": segments}
    out_dir=pathlib.Path("output")
    out_dir.mkdir(parents=True, exist_ok=True)
    plan_path=out_dir / "plan.json"
    with open(plan_path,"w",encoding="utf-8") as f:
        json.dump(plan, f, ensure_ascii=False, indent=2)
    narr_path=out_dir / "narration.txt"
    narr_path.write_text(master_bn, encoding="utf-8")
    print(f"Wrote {plan_path} and {narr_path}")
    try:
        # # ensure_outputs_tabs()
    except Exception as e:
        print(f"Warning ensure tabs failed: {e}")
    print(f"Plan done: {video_label} words {total_words} sec {total_sec} segments {len(segments)}")
def run_video():
    from brain.video_engine import run_video_job
    plan_path=pathlib.Path("output/plan.json")
    if not plan_path.exists():
        alt=pathlib.Path("plan.json")
        if alt.exists():
            plan_path=alt
        else:
            raise RuntimeError("plan.json missing, video job needs plan artifact")
    exit_code=run_video_job(str(plan_path))
    import sys
    sys.exit(exit_code)
if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["plan","video"], required=True)
    args=parser.parse_args()
    if args.mode=="plan":
        run_plan()
    else:
        run_video()
