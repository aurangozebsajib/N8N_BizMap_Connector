import os
import sys
import argparse
import requests

def run_plan():
    print("Running plan mode successfully...")

def send_video_to_telegram(file_path, caption=""):
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHANNEL_ID")
    if not bot_token or not chat_id:
        print("Telegram credentials missing.")
        return False
    url = f"https://api.telegram.org/bot{bot_token}/sendVideo"
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return False
    try:
        with open(file_path, "rb") as vf:
            response = requests.post(url, data={"chat_id": chat_id, "caption": caption}, files={"video": vf})
            if response.status_code == 200:
                print("Successfully sent video to Telegram!")
                return True
            else:
                print(f"Telegram API Error: {response.text}")
                return False
    except Exception as e:
        print(f"Exception during Telegram send: {e}")
        return False

def run_video_mode():
    print("Running video generation mode...")
    target_file = "output_clip.mp4"
    if not os.path.exists(target_file): open(target_file, "w").close()  # Create dummy file
    send_video_to_telegram(target_file, caption="🎬 BizMap Automation: Pipeline Test Successful! 🚀")

def main():
    parser = argparse.ArgumentParser(description="Brain Factory Main Runner")
    parser.add_argument("--mode", type=str, default="plan", help="Execution mode")
    args = parser.parse_args()
    
    if args.mode == "plan":
        run_plan()
    elif args.mode == "video":
        run_video_mode()
    else:
        print(f"Executing mode: {args.mode}")

if __name__ == "__main__":
    main()
