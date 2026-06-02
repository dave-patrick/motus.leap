import os
import sys
import time
import json
import subprocess
import threading
from datetime import datetime
import requests

# Shared state to communicate with server.py
active_job = None
job_lock = threading.Lock()

def send_webhook_notification(message, is_error=False):
    settings_path = os.path.join(os.path.dirname(__file__), "settings.json")
    if not os.path.exists(settings_path):
        return
        
    try:
        with open(settings_path, "r") as f:
            settings = json.load(f)
            
        webhook_url = settings.get("notification_webhook")
        if not webhook_url:
            return
            
        payload = {
            "content": f"🔔 **YouTube Playlist Agent**: {message}" if not is_error else f"⚠️ **YouTube Playlist Agent Error**: {message}"
        }
        
        requests.post(webhook_url, json=payload, timeout=5)
    except Exception as e:
        print(f"Failed to send webhook: {e}")

def run_pipeline_sequence():
    global active_job
    with job_lock:
        if active_job:
            print("Scheduler: Pipeline already running. Skipping scheduled trigger.")
            return
        active_job = "scheduled_pipeline"

    log_path = os.path.join(os.path.dirname(__file__), "agent_run.log")
    
    def log_message(msg):
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"\n[Scheduler Pipeline] {timestamp} - {msg}\n")
        print(f"[Scheduler Pipeline] {msg}")

    try:
        log_message("Starting scheduled pipeline: scan -> auto_sort -> generate_maintenance -> apply_maintenance")
        
        # 1. Scan
        log_message("Step 1/4: Scanning playlists...")
        proc = subprocess.run([sys.executable, "cli.py", "scan"], capture_output=True, text=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(proc.stdout)
            f.write(proc.stderr)
            
        # 2. Auto Sort
        log_message("Step 2/4: Auto-sorting Watch Later...")
        proc = subprocess.run([sys.executable, "cli.py", "auto-sort"], capture_output=True, text=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(proc.stdout)
            f.write(proc.stderr)
            
        # 3. Generate Maintenance
        log_message("Step 3/4: Generating maintenance plan...")
        proc = subprocess.run([sys.executable, "generate_maintenance.py"], capture_output=True, text=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(proc.stdout)
            f.write(proc.stderr)
            
        # 4. Apply Maintenance
        log_message("Step 4/4: Applying maintenance actions...")
        proc = subprocess.run([sys.executable, "apply_maintenance.py", "--force"], capture_output=True, text=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(proc.stdout)
            f.write(proc.stderr)
            
        log_message("Scheduled pipeline completed successfully!")
        
        # Save last run timestamp
        try:
            with open(os.path.join(os.path.dirname(__file__), "last_run.txt"), "w") as lf:
                lf.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        except:
            pass
            
        send_webhook_notification("Scheduled playlist maintenance pipeline completed successfully!")
        
    except Exception as e:
        log_message(f"Error in scheduled pipeline: {e}")
        send_webhook_notification(f"Scheduled playlist maintenance pipeline failed: {e}", is_error=True)
    finally:
        with job_lock:
            active_job = None

def run_scheduler_loop():
    print("Scheduler thread started: Checking daily at 5:00 PM and 11:00 PM...")
    last_scheduled_hour = -1
    last_scheduled_day = -1
    
    while True:
        now = datetime.now()
        current_hour = now.hour
        current_minute = now.minute
        current_day = now.day
        
        # 17 = 5 PM, 23 = 11 PM
        if current_hour in [17, 23] and current_minute == 0:
            if last_scheduled_hour != current_hour or last_scheduled_day != current_day:
                last_scheduled_hour = current_hour
                last_scheduled_day = current_day
                
                print(f"Scheduler: Triggering scheduled run for {current_hour}:00...")
                # Start pipeline in a separate thread so it doesn't block the scheduler loop
                threading.Thread(target=run_pipeline_sequence, daemon=True).start()
                
        time.sleep(30)

def start_scheduler():
    t = threading.Thread(target=run_scheduler_loop, daemon=True)
    t.start()
    return t
