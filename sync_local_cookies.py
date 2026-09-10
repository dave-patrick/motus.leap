import os
import sys
import json
import subprocess

import shutil
import sqlite3
import base64
try:
    import win32crypt
except ImportError:
    print("Installing pywin32...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pywin32"])
    import win32crypt
try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
except ImportError:
    print("Installing cryptography...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "cryptography"])
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# Extract cookies custom logic
yt_cookies = []

# 1. Prioritize manually exported cookies from the Downloads directory if available
downloads_cookie_path = r"C:\Users\davem\Downloads\www.youtube.com_cookies.txt"
if os.path.exists(downloads_cookie_path):
    print(f"Found manually exported cookies at {downloads_cookie_path}. Parsing cookies...")
    try:
        with open(downloads_cookie_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read().strip()
        
        if content.startswith("["):
            # It's JSON!
            json_cookies = json.loads(content)
            for jc in json_cookies:
                name = jc.get("name")
                value = jc.get("value")
                domain = jc.get("domain")
                path = jc.get("path", "/")
                secure = jc.get("secure", False)
                http_only = jc.get("httpOnly", False)
                expires = jc.get("expirationDate", 0)
                
                if domain and any(x in domain for x in ["youtube", "google", "goog"]):
                    yt_cookies.append({
                        "name": name,
                        "value": value,
                        "domain": domain,
                        "path": path,
                        "expires": int(expires) if expires else 0,
                        "secure": secure,
                        "httpOnly": http_only
                    })
            print(f"Successfully loaded {len(yt_cookies)} cookies from manually exported JSON file.")
        else:
            # Netscape format
            for line in content.splitlines():
                line = line.strip()
                if not line:
                    continue
                http_only = False
                if line.startswith("#HttpOnly_"):
                    http_only = True
                    line = line[len("#HttpOnly_"):]
                elif line.startswith("#"):
                    continue
                
                parts = line.split("\t")
                if len(parts) >= 7:
                    domain = parts[0]
                    path = parts[2]
                    secure = parts[3].upper() == "TRUE"
                    expires = int(parts[4]) if parts[4].isdigit() or (parts[4].startswith("-") and parts[4][1:].isdigit()) else 0
                    name = parts[5]
                    value = parts[6]
                    
                    if any(x in domain for x in ["youtube", "google", "goog"]):
                        yt_cookies.append({
                            "name": name,
                            "value": value,
                            "domain": domain,
                            "path": path,
                            "expires": expires,
                            "secure": secure,
                            "httpOnly": http_only
                        })
            print(f"Successfully loaded {len(yt_cookies)} cookies from manually exported Netscape file.")
    except Exception as e:
        print(f"Error parsing manual cookie file: {e}")

# 2. If no cookies found in Downloads or if they are invalid, fallback to local Chrome/Edge SQLite DBs
if not any(c["name"] == "SID" and c["value"] for c in yt_cookies):
    print("No valid manual session cookies found. Attempting to extract cookies from local browsers...")
    db_cookies = []
    appdata = os.environ.get("LOCALAPPDATA", r"C:\Users\davem\AppData\Local")
    browsers = {
        "Chrome": {
            "state": os.path.join(appdata, r"Google\Chrome\User Data\Local State"),
            "cookies": os.path.join(appdata, r"Google\Chrome\User Data\Default\Network\Cookies")
        },
        "Edge": {
            "state": os.path.join(appdata, r"Microsoft\Edge\User Data\Local State"),
            "cookies": os.path.join(appdata, r"Microsoft\Edge\User Data\Default\Network\Cookies")
        }
    }
    
    for name, paths in browsers.items():
        state_path = paths["state"]
        db_path = paths["cookies"]
        if not os.path.exists(state_path) or not os.path.exists(db_path):
            continue
            
        print(f"Checking {name}...")
        try:
            # 1. Get Key
            with open(state_path, "r", encoding="utf-8") as f:
                local_state = json.load(f)
            encrypted_key = base64.b64decode(local_state["os_crypt"]["encrypted_key"])[5:]
            decrypted_key = win32crypt.CryptUnprotectData(encrypted_key, None, None, None, 0)[1]
            
            # 2. Copy Database to temp to avoid lock
            temp_db = os.path.join(os.environ.get("TEMP", "."), f"temp_{name.lower()}_cookies.db")
            try:
                shutil.copy2(db_path, temp_db)
            except Exception as ce:
                print(f"Could not read active database for {name} (locked). Fallback to shadow copy or user action.")
                continue
            
            # 3. Read cookies
            conn = sqlite3.connect(temp_db)
            cursor = conn.cursor()
            cursor.execute("SELECT host_key, name, value, encrypted_value, path, is_secure, is_httponly, expires_utc FROM cookies")
            rows = cursor.fetchall()
            
            count = 0
            for host, cname, val, enc_val, path, secure, http_only, expires in rows:
                if any(x in host for x in ["youtube", "google", "goog"]):
                    decrypted_val = ""
                    if enc_val:
                        try:
                            if enc_val.startswith(b"v10") or enc_val.startswith(b"v11"):
                                nonce = enc_val[3:15]
                                ciphertext = enc_val[15:]
                                aesgcm = AESGCM(decrypted_key)
                                decrypted_val = aesgcm.decrypt(nonce, ciphertext, None).decode("utf-8")
                            else:
                                decrypted_val = win32crypt.CryptUnprotectData(enc_val, None, None, None, 0)[1].decode("utf-8")
                        except Exception as de:
                            decrypted_val = val if val else ""
                    else:
                        decrypted_val = val if val else ""
                        
                    # expires is microseconds since Jan 1, 1601. Convert to unix epoch seconds.
                    exp_seconds = expires // 1000000 - 11644473600 if expires > 0 else -1
                    db_cookies.append({
                        "name": cname,
                        "value": decrypted_val,
                        "domain": host,
                        "path": path,
                        "expires": exp_seconds,
                        "secure": bool(secure),
                        "httpOnly": bool(http_only)
                    })
                    count += 1
            conn.close()
            try: os.remove(temp_db)
            except: pass
            print(f"Successfully extracted {count} cookies from {name}")
        except Exception as e:
            print(f"Failed to extract from {name}: {e}")
            
    # If browser DB extraction got a valid session, use it
    if any(c["name"] == "SID" and c["value"] for c in db_cookies):
        yt_cookies = db_cookies
    else:
        print("Warning: Browser DB extraction did not yield an authenticated SID cookie (likely due to App-Bound Encryption).")

# 3. Final verification to protect the remote VM from being overwritten with unauthenticated/junk cookies
has_auth = any(c["name"] in ["SID", "__Secure-3PSID", "__Secure-1PSID"] and c["value"] for c in yt_cookies)
if not has_auth:
    print("\n[CRITICAL ERROR] No authenticated session cookie (SID or __Secure-3PSID) found in manual file or local browsers.")
    print("Aborting sync to prevent overwriting the active working YouTube session on the remote VM with unauthenticated cookies.")
    sys.exit(0)

print(f"Extracted/loaded {len(yt_cookies)} cookies.")

# Save temporary json file
local_json_path = os.path.join(os.path.dirname(__file__), "temp_cookies.json")
with open(local_json_path, "w", encoding="utf-8") as f:
    json.dump(yt_cookies, f, indent=2)

# Save temporary txt file (Netscape format)
local_txt_path = os.path.join(os.path.dirname(__file__), "temp_cookies.txt")
with open(local_txt_path, "w", encoding="utf-8") as f:
    f.write("# Netscape HTTP Cookie File\n")
    for c in yt_cookies:
        http_only_prefix = "#HttpOnly_" if c.get("httpOnly") else ""
        secure_str = "TRUE" if c.get("secure") else "FALSE"
        exp = int(c.get("expires", -1)) if c.get("expires", -1) > 0 else 0
        f.write(f"{http_only_prefix}{c['domain']}\tTRUE\t{c['path']}\t{secure_str}\t{exp}\t{c['name']}\t{c['value']}\n")

# Save local copies to ~/.camofox/cookies/
try:
    local_camofox_dir = os.path.expanduser("~/.camofox/cookies")
    os.makedirs(local_camofox_dir, exist_ok=True)
    with open(os.path.join(local_camofox_dir, "cookies.json"), "w", encoding="utf-8") as f:
        json.dump(yt_cookies, f, indent=2)
    with open(os.path.join(local_camofox_dir, "cookies.txt"), "w", encoding="utf-8") as f:
        f.write("# Netscape HTTP Cookie File\n")
        for c in yt_cookies:
            http_only_prefix = "#HttpOnly_" if c.get("httpOnly") else ""
            secure_str = "TRUE" if c.get("secure") else "FALSE"
            exp = int(c.get("expires", -1)) if c.get("expires", -1) > 0 else 0
            f.write(f"{http_only_prefix}{c['domain']}\tTRUE\t{c['path']}\t{secure_str}\t{exp}\t{c['name']}\t{c['value']}\n")
    print(f"Saved cookies locally to {local_camofox_dir}")
except Exception as le:
    print(f"Warning: Failed to save cookies locally: {le}")

# SSH and SCP setup
ssh_key = r"C:\Users\davem\My Drive\ssh-key-2026-06-02.key"
remote_host = "ubuntu@161.153.18.209"

print("Uploading cookies to remote server...")
# Upload JSON
subprocess.run([
    "scp", "-F", "NUL", "-o", "StrictHostKeyChecking=no", "-i", ssh_key,
    local_json_path, f"{remote_host}:/home/ubuntu/.camofox/cookies/cookies.json"
], check=True)

# Upload TXT
subprocess.run([
    "scp", "-F", "NUL", "-o", "StrictHostKeyChecking=no", "-i", ssh_key,
    local_txt_path, f"{remote_host}:/home/ubuntu/.camofox/cookies/cookies.txt"
], check=True)

# Update active Camofox session
print("Activating cookies in current Camofox session (optional)...")
ssh_cmd = (
    "curl -s -X POST -H 'Authorization: Bearer my_secret_cookie_key' "
    "-H 'Content-Type: application/json' "
    "-d @/home/ubuntu/.camofox/cookies/cookies.json "
    "http://localhost:9377/sessions/yt_playlist_agent_default/cookies"
)
try:
    subprocess.run([
        "ssh", "-F", "NUL", "-o", "StrictHostKeyChecking=no", "-i", ssh_key,
        remote_host, ssh_cmd
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("Camofox session updated successfully.")
except Exception as se:
    print("Warning: Active Camofox session not updated (Camofox server might be stopped).")

# Clean up local temporary files
try:
    os.remove(local_json_path)
    os.remove(local_txt_path)
except:
    pass

print("Cookies synced successfully!")
