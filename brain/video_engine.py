import os
import pathlib
import json
import subprocess
import shutil
import brain.config as cfg
from brain.sheets import load_hf_keys, load_model_routing
from brain.hf_client import HFPool

def generate_valid_video_clip(file_path, duration=3, label="BizMap AI Video"):
    """
    Generates a valid, playable MP4 video with exact duration, video stream,
    and audio track using ffmpeg so video duration is NEVER 0:00.
    """
    pathlib.Path(file_path).parent.mkdir(parents=True, exist_ok=True)
    dur = max(2, int(duration))

    # Clean label for safe ffmpeg command
    safe_label = "".join(c for c in label if c.isalnum() or c in (" ", "-", "_", "."))[:30] or "BizMap Video"

    if shutil.which("ffmpeg"):
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"color=c=0x0f172a:s=720x1280:d={dur}:r=25",
            "-f", "lavfi", "-i", f"anullsrc=channel_layout=stereo:sample_rate=44100:d={dur}",
            "-vf", f"drawtext=text='{safe_label}':fontcolor=white:fontsize=28:x=(w-text_w)/2:y=(h-text_h)/2",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "64k",
            "-shortest",
            file_path
        ]
        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=25)
            if res.returncode == 0 and os.path.exists(file_path) and os.path.getsize(file_path) > 1024:
                return True
        except Exception as e:
            print(f"ffmpeg render error: {e}")

    # Fallback to minimal valid video
    return False

def run_video_job(plan_path):
    """
    Main Video Engine
    1. Loads HF keys from Google Sheet ('Api_keys_Sheet' -> 'Video API')
    2. Initializes HFPool
    3. Generates character reference image via HF text-to-image
    4. For each segment, calls HF text-to-video / image-to-video
    5. Saves real video bytes or fallback video
    6. Writes manifest.json
    """
    if not os.path.exists(plan_path):
        print(f"❌ Error: plan file does not exist at {plan_path}")
        return 1

    with open(plan_path, "r", encoding="utf-8") as f:
        plan = json.load(f)

    video_label = plan.get("video_label", "BizMap Video")
    dialect = plan.get("dialect_used", "none")
    character = plan.get("character", {})
    char_desc = character.get("description", "")
    char_mode = character.get("mode", "per_video")
    segments = plan.get("segments", [])

    out_dir = pathlib.Path("output/video")
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n=======================================================")
    print(f"🎬 Running Video Engine for: {video_label}")
    print(f"   Dialect: {dialect} | Segments: {len(segments)}")
    print(f"=======================================================")

    # 1. Load Hugging Face API keys from Google Sheet ('Video API' tab)
    hf_keys = load_hf_keys()
    hf_pool = HFPool(hf_keys)
    routing = load_model_routing()

    # 2. Character Reference Image (for image-to-video)
    ref_image_path = out_dir / "character_ref.png"
    ref_ok = False
    
    fixed_ref_asset = pathlib.Path("brain/assets/host_reference.png")
    if char_mode == "fixed" and fixed_ref_asset.exists():
        shutil.copy(str(fixed_ref_asset), str(ref_image_path))
        ref_ok = True
        print(f"✅ Using fixed host reference image: {ref_image_path}")
    elif hf_keys:
        t2i_models = routing.get("text-to-image", [])
        char_prompt = f"{char_desc}, portrait, centered, plain simple background, clean semi-realistic 2D illustration"
        for m in t2i_models:
            mid = m["model_id"]
            print(f"🎨 Generating character reference image via HF ({mid})...")
            ok, used_mid = hf_pool.call_text_to_image(mid, char_prompt, str(ref_image_path))
            if ok and ref_image_path.exists() and os.path.getsize(str(ref_image_path)) > 1024:
                ref_ok = True
                print(f"✅ Character reference image generated successfully!")
                break

    # 3. Process each segment
    manifest = []
    success_any = False

    for seg in segments:
        seg_id = seg["segment_id"]
        vtype = seg.get("video_type", "text-to-video")
        planned_dur = seg.get("planned_duration_sec", 3.0)
        visual_prompt = seg.get("visual_prompt", "")
        full_prompt = f"{visual_prompt}, {seg.get('style_notes', '')}, {char_desc}"[:500]

        out_name = f"segment_{seg_id:02d}_{vtype}.mp4"
        out_path = out_dir / out_name

        status = "failed"
        model_used = "none"
        generated_by_hf = False

        print(f"\n▶ Processing Segment {seg_id}/{len(segments)} [{vtype}] ({planned_dur}s)")
        print(f"  Prompt: {visual_prompt[:70]}...")

        # A. Try Hugging Face API if keys are available
        if hf_keys and vtype in ("text-to-video", "image-to-video"):
            candidate_models = routing.get(vtype, [])
            for m_entry in candidate_models:
                mid = m_entry["model_id"]
                print(f"  ⚡ Calling Hugging Face model: {mid}...")

                ref_for_call = str(ref_image_path) if (vtype == "image-to-video" and ref_ok) else None
                ok, used = hf_pool.call_video(mid, full_prompt, str(out_path), ref_image_path=ref_for_call)
                
                if ok and os.path.exists(str(out_path)) and os.path.getsize(str(out_path)) >= 5 * 1024:
                    status = "success-hf"
                    model_used = mid
                    generated_by_hf = True
                    success_any = True
                    print(f"  ✅ Segment {seg_id} generated via Hugging Face ({os.path.getsize(str(out_path))} bytes)")
                    break

        # B. Fallback Local Rendering (Exact duration, never 0:00)
        if not generated_by_hf:
            print(f"  ⚠️ Using local rendering fallback for Segment {seg_id} ({planned_dur}s)...")
            fallback_label = f"BizMap Seg {seg_id}: {vtype}"
            ok = generate_valid_video_clip(str(out_path), duration=planned_dur, label=fallback_label)
            if ok and os.path.exists(str(out_path)) and os.path.getsize(str(out_path)) > 1024:
                status = "success-local-fallback"
                model_used = "local-ffmpeg-renderer"
                success_any = True
                print(f"  ✅ Segment {seg_id} fallback created: {out_name} (Size: {os.path.getsize(str(out_path))} bytes, Dur: {planned_dur}s)")

        manifest.append({
            "segment_id": seg_id,
            "video_type": vtype,
            "output_file": str(out_name),
            "planned_duration_sec": planned_dur,
            "actual_size_bytes": os.path.getsize(str(out_path)) if os.path.exists(str(out_path)) else 0,
            "status": status,
            "model_used": model_used
        })

    # 4. Save manifest.json
    manifest_path = out_dir / "manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump({
            "video_label": video_label,
            "total_segments": len(segments),
            "hf_keys_loaded": len(hf_keys),
            "success": success_any,
            "segments": manifest
        }, f, indent=2)

    print(f"\n✅ Video Job Finished. Manifest saved to {manifest_path}")
    return 0 if success_any else 1
