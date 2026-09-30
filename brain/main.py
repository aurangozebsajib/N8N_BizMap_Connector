import os
import sys
import json
import pathlib
import argparse
import urllib.request
import urllib.parse

# Try importing requests; fallback gracefully if not installed
try:
    import requests
except ImportError:
    requests = None

# Robust import of planner and video_engine
try:
    from brain.planner import run_plan
except ImportError:
    sys.path.insert(0, os.path.abspath("."))
    from brain.planner import run_plan

try:
    from brain.video_engine import run_video_job
except ImportError:
    sys.path.insert(0, os.path.abspath("."))
    from brain.video_engine import run_video_job

def send_video_to_telegram(file_path, caption=""):
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHANNEL_ID")
    
    if not bot_token or not chat_id:
        print("⚠️ Telegram credentials missing (TELEGRAM_BOT_TOKEN or TELEGRAM_CHANNEL_ID not set).")
        return False
        
    url = f"https://api.telegram.org/bot{bot_token}/sendVideo"
    if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
        print(f"❌ Video file missing or empty (0 bytes): {file_path}")
        return False
        
    print(f"🚀 Sending video to Telegram: {file_path} (Size: {os.path.getsize(file_path)} bytes)...")
    
    if requests is not None:
        try:
            with open(file_path, "rb") as vf:
                response = requests.post(
                    url,
                    data={"chat_id": chat_id, "caption": caption},
                    files={"video": vf},
                    timeout=120
                )
                if response.status_code == 200:
                    print("✅ Successfully sent real AI marketing video to Telegram group!")
                    return True
                else:
                    print(f"❌ Telegram API Error ({response.status_code}): {response.text}")
                    return False
        except Exception as e:
            print(f"❌ Exception during Telegram send: {e}")
            return False
    else:
        # Fallback using standard library urllib multipart
        boundary = "----BizMapFormBoundary" + str(int(os.path.getmtime(file_path)))
        body = []
        body.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"chat_id\"\r\n\r\n{chat_id}\r\n".encode("utf-8"))
        if caption:
            body.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"caption\"\r\n\r\n{caption}\r\n".encode("utf-8"))
        
        filename = os.path.basename(file_path)
        body.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"video\"; filename=\"{filename}\"\r\nContent-Type: video/mp4\r\n\r\n".encode("utf-8"))
        with open(file_path, "rb") as f:
            body.append(f.read())
        body.append(f"\r\n--{boundary}--\r\n".encode("utf-8"))
        
        data = b"".join(body)
        req = urllib.request.Request(url, data=data)
        req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                if resp.status == 200:
                    print("✅ Successfully sent real AI marketing video to Telegram group!")
                    return True
        except Exception as e:
            print(f"❌ Exception during Telegram send via urllib: {e}")
            return False

def run_video_mode():
    print("=== Running AI Video Mode ===")
    
    # Locate plan.json
    plan_paths = [
        "output/plan.json",
        "output/plan/plan.json",
        "plan.json",
        "brain/output/plan.json"
    ]
    plan_file = None
    for p in plan_paths:
        if os.path.exists(p):
            plan_file = p
            break
            
    if not plan_file:
        print("⚠️ plan.json not found. Running plan mode first...")
        try:
            run_plan()
        except Exception as e:
            print(f"Error running plan: {e}")
            
        for p in plan_paths:
            if os.path.exists(p):
                plan_file = p
                break
                
    if not plan_file or not os.path.exists(plan_file):
        print("❌ Error: Could not locate plan.json for video generation.")
        sys.exit(1)
        
    print(f"Using plan file: {plan_file}")
    
    # Call video engine to render videos from Hugging Face or fallback
    status_code = run_video_job(plan_file)
    if status_code != 0:
        print("❌ Video generation failed or returned non-zero status.")
        sys.exit(status_code)
        
    print("✅ Video generation completed. Dispatching generated videos to Telegram...")
    
    video_dir = pathlib.Path("output/video")
    if video_dir.exists():
        video_files = sorted(list(video_dir.glob("*.mp4")))
        if not video_files:
            print("⚠️ No .mp4 files found in output/video/")
        for vfile in video_files:
            if vfile.stat().st_size > 0:
                caption = f"🎬 BizMap AI Marketing Video: {vfile.name} 🚀"
                send_video_to_telegram(str(vfile), caption=caption)
            else:
                print(f"Skipping empty file: {vfile.name}")
    else:
        print("⚠️ output/video directory not found.")

def main():
    parser = argparse.ArgumentParser(description="N8N BizMap Connector Brain")
    parser.add_argument("--mode", default="all", choices=["plan", "video", "all"], help="Execution mode (plan, video, all)")
    args = parser.parse_args()

    if args.mode == "plan":
        print("=== Executing Plan Mode ===")
        run_plan()
        print("Running plan mode successfully...")
    elif args.mode == "video":
        print("=== Executing Video Mode ===")
        run_video_mode()
    elif args.mode == "all":
        print("=== Executing Full Pipeline (Plan + Video + Dispatch) ===")
        run_plan()
        run_video_mode()
    else:
        print(f"Unknown mode: {args.mode}")
        sys.exit(1)

if __name__ == "__main__":
    main()
