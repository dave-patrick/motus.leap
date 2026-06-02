import subprocess
import json
import os
import sys

def cleanup():
    print("Searching for running Chrome processes...")
    try:
        # Query Win32_Process via PowerShell to get ProcessId and CommandLine
        cmd = ["powershell", "-NoProfile", "-Command", 
               "Get-CimInstance Win32_Process -Filter \"Name = 'chrome.exe'\" | ForEach-Object { [PSCustomObject]@{ Id = $_.ProcessId; CommandLine = $_.CommandLine } } | ConvertTo-Json"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        output = result.stdout.strip()
        if not output:
            print("No chrome.exe processes found.")
            return
            
        # Parse the JSON output
        try:
            processes = json.loads(output)
        except json.JSONDecodeError:
            # ConvertTo-Json might output a single object instead of an array if there's only one process
            if output.startswith("{"):
                processes = [json.loads(output)]
            else:
                print(f"Could not parse PowerShell output: {output}")
                return
                
        # Target user_data directory
        target_dir = os.path.abspath("user_data")
        target_dir_lower = target_dir.lower()
        print(f"Target profile directory: {target_dir}")
        
        killed_count = 0
        for p in processes:
            pid = p.get("Id")
            cmdline = p.get("CommandLine") or ""
            if target_dir_lower in cmdline.lower():
                print(f"Found matching Chrome process {pid} with command line: {cmdline}")
                # Kill process
                try:
                    subprocess.run(["taskkill", "/F", "/PID", str(pid)], check=True, capture_output=True)
                    print(f"  Successfully killed process {pid}")
                    killed_count += 1
                except subprocess.CalledProcessError as ke:
                    print(f"  Failed to kill process {pid}: {ke.stderr}")
                    
        print(f"Cleaned up {killed_count} agent Chrome processes.")
        
        # Also clean up any chromedriver.exe processes
        try:
            print("Cleaning up chromedriver.exe processes...")
            subprocess.run(["taskkill", "/F", "/IM", "chromedriver.exe", "/T"], capture_output=True)
        except Exception:
            pass
            
    except Exception as e:
        print(f"Error during cleanup: {e}")

if __name__ == "__main__":
    cleanup()
