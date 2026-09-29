import os
import sys
import argparse

def run_plan():
    print("Running plan mode successfully...")
    # এখানে আপনার মূল প্ল্যান লজিক থাকবে যা ব্রেইনকে ইনিশিয়ালাইজ করবে

def main():
    parser = argparse.ArgumentParser(description="Brain Factory Main Runner")
    parser.add_argument("--mode", type=str, default="plan", help="Execution mode")
    args = parser.parse_args()
    
    if args.mode == "plan":
        run_plan()
    else:
        print(f"Executing mode: {args.mode}")

if __name__ == "__main__":
    main()
