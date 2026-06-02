import os
import sys
import json
import sqlite3
import base64
import win32crypt
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# Paths
LOCAL_STATE_PATH = os.path.abspath("user_data/Local State")
COOKIES_DB_PATH = os.path.abspath("user_data/Default/Network/Cookies")

def get_master_key(local_state_path):
    with open(local_state_path, "r", encoding="utf-8") as f:
        local_state = json.loads(f.read())
    encrypted_key = base64.b64decode(local_state["os_crypt"]["encrypted_key"])
    # Remove DPAPI prefix 'DPAPI'
    encrypted_key = encrypted_key[5:]
    # Decrypt key using Windows DPAPI
    decrypted_key = win32crypt.CryptUnprotectData(encrypted_key, None, None, None, 0)[1]
    return decrypted_key

def decrypt_cookie(encrypted_value, master_key):
    try:
        # Check signature v10/v11
        if encrypted_value[:3] in (b'v10', b'v11'):
            iv = encrypted_value[3:15]
            ciphertext = encrypted_value[15:]
            aesgcm = AESGCM(master_key)
            decrypted = aesgcm.decrypt(iv, ciphertext, None)
            try:
                # In Chrome 120+, the first 32 bytes of decrypted data are a header/signature.
                # The actual cookie value starts at byte 32.
                return decrypted[32:].decode("utf-8")
            except UnicodeDecodeError:
                try:
                    # Fallback to decoding the entire decrypted data (for older versions)
                    return decrypted.decode("utf-8")
                except UnicodeDecodeError:
                    print(f"Decrypted bytes (not UTF-8): {decrypted[:50]}")
                    return None
        else:
            # DPAPI decryption for older formats
            decrypted = win32crypt.CryptUnprotectData(encrypted_value, None, None, None, 0)[1]
            return decrypted.decode("utf-8")
    except Exception as e:
        print(f"Error decrypting cookie: {e}")
        return None

def get_cookies():
    try:
        master_key = get_master_key(LOCAL_STATE_PATH)
    except Exception as e:
        print(f"Error getting master key: {e}")
        return []

    conn = sqlite3.connect(COOKIES_DB_PATH)
    cursor = conn.cursor()
    
    # Try different table schemes (host_key vs host in older versions)
    try:
        cursor.execute("SELECT host_key, name, path, encrypted_value, expires_utc, is_secure, is_httponly FROM cookies")
    except sqlite3.OperationalError:
        cursor.execute("SELECT host, name, path, encrypted_value, expires_utc, secure, httponly FROM cookies")

    cookies = []
    for host_key, name, path, encrypted_value, expires_utc, is_secure, is_httponly in cursor.fetchall():
        decrypted_val = decrypt_cookie(encrypted_value, master_key)
        if decrypted_val is not None:
            # Playwright cookie format:
            # {name: str, value: str, domain: str, path: str, expires: float, httpOnly: bool, secure: bool}
            # Convert expires_utc (Chrome uses microsecond epoch since 1601) to unix timestamp
            # expires_utc = 0 means session cookie, expires = -1 in Playwright
            expires = -1
            if expires_utc > 0:
                expires = (expires_utc / 1000000.0) - 11644473600.0
            
            cookies.append({
                "name": name,
                "value": decrypted_val,
                "domain": host_key,
                "path": path,
                "expires": expires,
                "httpOnly": bool(is_httponly),
                "secure": bool(is_secure)
            })
            
    conn.close()
    return cookies

if __name__ == "__main__":
    cookies = get_cookies()
    print(f"Successfully decrypted {len(cookies)} cookies.")
    # Print youtube related cookies
    yt_cookies = [c for c in cookies if "youtube.com" in c["domain"]]
    print(f"Found {len(yt_cookies)} YouTube cookies.")
    if yt_cookies:
        print("Sample cookie name:", yt_cookies[0]["name"])
