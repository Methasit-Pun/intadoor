#!/usr/bin/env python3
import os, time, sys, RPi.GPIO as GPIO
from supabase import create_client
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

RELAY_PIN = 17
DOOR_OPEN_DURATION = 6
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")
TABLE_NAME = os.getenv("SUPABASE_TABLE", "reservations")
ACCESS_LOG_TABLE = "access_logs"
QR_COLUMN = "qr_code_url"
EMERGENCY_CODES = [
    "INR012509101700000201",
    "INR012508300900000131"
]

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)
GPIO.setup(RELAY_PIN, GPIO.OUT, initial=GPIO.LOW)

def connect_supabase():
    try:
        return create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        print(f"❌ Supabase init error: {e}")
        return None

supabase = connect_supabase()
print("🚪 Door control system started.\n")

def safe_flush():
    try:
        sys.stdout.flush()
    except:
        pass

def open_door():
    try:
        print("🔓 Door unlocked")
        GPIO.output(RELAY_PIN, GPIO.HIGH)
        safe_flush()
        time.sleep(DOOR_OPEN_DURATION)
        GPIO.output(RELAY_PIN, GPIO.LOW)
        print("🔒 Door locked again")
    except Exception as e:
        print(f"⚠️ GPIO error: {e}")
        GPIO.cleanup()
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(RELAY_PIN, GPIO.OUT, initial=GPIO.LOW)

def check_code(code):
    global supabase
    if not supabase:
        supabase = connect_supabase()
        if not supabase:
            return False
    try:
        res = supabase.table(TABLE_NAME).select("*").eq(QR_COLUMN, code.strip()).execute()
        return bool(res.data)
    except Exception as e:
        print(f"❌ Database error: {e}")
        supabase = None
        return False

def log_access(code, success):
    global supabase
    if not supabase:
        supabase = connect_supabase()
        if not supabase:
            return
    try:
        supabase.table(ACCESS_LOG_TABLE).insert({
            "qr_code_url": code,
            "timestamp": datetime.now().isoformat(),
            "success": success,
            "device": os.getenv("DEVICE_NAME", "raspberry_pi_door"),
            "access_type": "door_entry"
        }).execute()
    except Exception as e:
        print(f"⚠️ Log insert failed: {e}")

last_action = time.time()
try:
    while True:
        try:
            code = input("Scan QR code (or type 'quit' to exit): ").strip()
        except EOFError:
            print("⚠️ Input stream closed, restarting...")
            time.sleep(2)
            continue
        except Exception as e:
            print(f"⚠️ Input error: {e}")
            time.sleep(2)
            continue

        if code.lower() == "quit":
            break

        if not code:
            print("⚠️ Empty input, try again.")
            continue

        print("🔍 Checking code...")
        safe_flush()
        authorized = code in EMERGENCY_CODES or check_code(code)
        if authorized:
            print("✅ Access granted")
            open_door()
            log_access(code, True)
        else:
            print("❌ Access denied")
            log_access(code, False)

        # Auto-refresh supabase every hour
        if time.time() - last_action > 3600:
            supabase = connect_supabase()
            last_action = time.time()

except KeyboardInterrupt:
    print("\n🛑 System stopped by user")

finally:
    GPIO.output(RELAY_PIN, GPIO.LOW)
    GPIO.cleanup()
    print("GPIO cleaned up. Door locked.")
