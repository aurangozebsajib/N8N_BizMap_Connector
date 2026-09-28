
import os, pathlib, json, shutil
import brain.config as cfg
from brain.sheets import load_hf_keys, load_model_routing, append_row_by_headers
from brain.hf_client import HFPool
from brain.text_animation import make_text_animation_clip, make_kenburns_clip, probe_duration, find_bengali_font
def run_video_job(plan_path):
    with open(plan_path, "r", encoding="utf-8") as f:
        plan=json.load(f)
    video_label=plan["video_label"]
    dialect=plan.get("dialect_used","none")
    character=plan.get("character",{})
    char_desc=character.get("description","")
    mode=character.get("mode","per_video")
    segments=plan.get("segments",[])
    out_dir=pathlib.Path("output/video")
    out_dir.mkdir(parents=True, exist_ok=True)
    hf_keys=load_hf_keys()
    routing=load_model_routing()
    hf_pool=HFPool(hf_keys)
    ref_path=out_dir / "character_ref.png"
    fixed_ref_src=pathlib.Path("brain/assets/host_reference.png")
    if mode=="fixed":
        if not fixed_ref_src.exists():
            raise RuntimeError("fixed mode but host_reference.png missing")
        shutil.copy(str(fixed_ref_src), str(ref_path))
        print(f"Copied fixed ref to {ref_path}")
        ref_ok=True
        ref_model="fixed-asset"
    else:
        # generate ref image
        models=routing.get("text-to-image",[])
        ref_ok=False
        ref_model=""
        prompt=f"{char_desc}, portrait, centered, plain simple background, clean semi-realistic 2D illustration"
        for m in models:
            mid=m["model_id"]
            ok, used = hf_pool.call_text_to_image(mid, prompt, str(ref_path))
            if ok:
                ref_ok=True
                ref_model=mid
                break
        if not ref_ok:
            print("Reference image generation failed")
            if not ref_path.exists():
                ref_ok=False
        else:
            print(f"Ref image ok {ref_model}")
    local_fallback=os.environ.get(cfg.LOCAL_FALLBACK_ENV,"true").lower()=="true"
    manifest=[]
    success_any=False
    summary=[]
    bengali_font=find_bengali_font()
    if not bengali_font:
        print("Warning: no Bengali font found")
    for seg in segments:
        seg_id=seg["segment_id"]
        vtype=seg["video_type"]
        prompt=seg.get("visual_prompt","")+" "+seg.get("style_notes","")+" "+char_desc
        prompt=prompt[:600]
        planned=seg.get("planned_duration_sec",3.0)
        out_file_name=f"segment_{seg_id:02d}_{vtype}.mp4"
        out_path=out_dir / out_file_name
        status="failed-no-model-available"
        model_used=""
        clip_dur=0.0
        if vtype=="text-animation":
            ok, st, dur = make_text_animation_clip(seg["text_portion"], str(out_path), planned, font_path=bengali_font)
            if ok:
                status="success-local"
                model_used="local-textanim"
                clip_dur=dur
                success_any=True
            else:
                status=st
        elif vtype in ("text-to-video","image-to-video"):
            task_models=routing.get(vtype,[])
            for m in task_models:
                mid=m["model_id"]
                if vtype=="image-to-video":
                    if not ref_path.exists():
                        status="failed-no-ref"
                        break
                    ok, used = hf_pool.call_video(mid, prompt, str(out_path), ref_image_path=str(ref_path))
                else:
                    ok, used = hf_pool.call_video(mid, prompt, str(out_path), ref_image_path=None)
                if ok:
                    status="success"
                    model_used=mid
                    clip_dur=probe_duration(str(out_path))
                    success_any=True
                    break
            if status!="success":
                if local_fallback:
                    if vtype=="image-to-video" and ref_path.exists():
                        ok, dur = make_kenburns_clip(str(ref_path), str(out_path), planned)
                        if ok:
                            status="fallback-kenburns"
                            model_used="local-kenburns"
                            clip_dur=dur
                            success_any=True
                    elif vtype=="text-to-video":
                        ok, st, dur = make_text_animation_clip(seg["text_portion"], str(out_path), planned, font_path=bengali_font)
                        if ok:
                            status="fallback-textcard"
                            model_used="local-textcard"
                            clip_dur=dur
                            success_any=True
                        else:
                            status=st
        if not out_path.exists():
            clip_dur=0.0
        row={"video_label": video_label,"segment_id": seg_id,"video_type": vtype,"start_sec": seg.get("start_sec",""),"end_sec": seg.get("end_sec",""),"planned_duration_sec": seg.get("planned_duration_sec",""),"clip_duration_sec": round(clip_dur,2) if clip_dur else "","model_used": model_used,"character_ref_image": str(ref_path) if ref_path.exists() else "","output_file": out_file_name if out_path.exists() else "","status": status,"dialect": dialect}
        try:
            append_row_by_headers("Video_Outputs", row)
        except Exception as e:
            print(f"Failed append Video_Outputs seg {seg_id}: {e}")
        manifest.append({"segment_id": seg_id,"file": out_file_name if out_path.exists() else "","video_type": vtype,"start_sec": seg.get("start_sec"),"end_sec": seg.get("end_sec"),"planned_duration_sec": seg.get("planned_duration_sec"),"clip_duration_sec": clip_dur,"model_used": model_used,"status": status})
        summary.append((seg_id, vtype, model_used, status))
    manifest_path=out_dir / "manifest.json"
    with open(manifest_path,"w",encoding="utf-8") as f:
        json.dump({"video_label":video_label,"dialect":dialect,"segments":manifest}, f, ensure_ascii=False, indent=2)
    print("\n=== VIDEO SUMMARY ===")
    print(f"{'seg':<5} {'type':<15} {'model':<30} {'status'}")
    for sid, vt, mu, st in summary:
        print(f"{sid:<5} {vt:<15} {mu[:30]:<30} {st}")
    print("=====================\n")
    if not success_any:
        print("All segments failed")
        return 1
    return 0
