import os
import sys
import json
import requests
import pathlib

from brain.planner import run_plan
from brain.video_engine import run_video_job

def send_video_to_telegram(file_path, caption=""):
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHANNEL_ID")
    if not bot_token or not chat_id:
        print("Telegram credentials missing.")
        return False
    url = f"https://api.telegram.org/bot{bot_token}/sendVideo"
    if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
        print(f"Video file missing or empty: {file_path}")
        return False
    
    print(f"Sending video to Telegram: {file_path} (Size: {os.path.getsize(file_path)} bytes)")
    try:
        with open(file_path, "rb") as vf:
            response = requests.post(
                url, 
                data={"chat_id": chat_id, "caption": caption}, 
                files={"video": vf},
                timeout=120
            )
            if response.status_code == 200:
                print("✅ Successfully sent real AI video to Telegram group!")
                return True
            else:
                print(f"❌ Telegram API Error: {response.text}")
                return False
    except Exception as e:
        print(f"❌ Exception during Telegram send: {e}")
        return False

def run_video_mode():
    print("Running real AI video generation mode...")
    
    # plan.json ফাইলের সঠিক পাথ খুঁজে বের করা
    plan_paths = ["output/plan.json", "plan.json", "brain/output/plan.json"]
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
        
    print(print(f"Using plan file: {plan_file}"))
    
    # ভিডিও ইঞ্জিন কল করে Hugging Face থেকে রিয়েল ভিডিও জেনারেট করা
    status_code = run_video_job(plan_file)
    if status_code != 0:
        print("❌ Video generation failed or returned non-zero status.")
        sys.exit(status_code)
        
    print("✅ Video generation completed. Dispatching generated videos to Telegram...")
    
    # output/video ফোল্ডার থেকে জেনারেট হওয়া আসল ভিডিও ফাইলগুলো টেলিগ্রামে পাঠানো
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
    import argparse
    parser = argparse.ArgumentParser(description="N8N BizMap Connector Brain")
    parser.add_argument("--mode", required=True, choices=["plan", "video"], help="Execution mode")
    args = parser.parse_args()

    if args.mode == "plan":
        print("=== Executing Plan Mode ===")
        run_plan()
        print("Running plan mode successfully...")
    elif args.mode == "video":
        print("=== Executing Video Mode ===")
        run_video_mode()
    else:
        print(f"Unknown mode: {args.mode}")
        sys.exit(1)

if __name__ == "__main__":
    main()
