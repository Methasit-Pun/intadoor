#!/usr/bin/env python3
import os, time, sys, RPi.GPIO as GPIO
from supabase import create_client
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()

RELAY_PIN = 17
DOOR_OPEN_DURATION = 6
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")
TABLE_NAME = os.getenv("SUPABASE_TABLE", "reservations")
ACCESS_LOG_TABLE = "access_logs"
QR_COLUMN = "qr_code_url"
DATE_COLUMN = "date"
START_TIME_COLUMN = "start_time"
END_TIME_COLUMN = "end_time"
CONF_NUMBER_COLUMN = "confirmation_number"
ACCESS_WINDOW_HOURS = 1  # hours before/after the booking block
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

def _parse_time(t_str):
    """Parse HH:MM:SS or HH:MM string into a datetime.time object."""
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(t_str, fmt).time()
        except ValueError:
            continue
    raise ValueError(f"Unrecognised time format: {t_str}")


def check_code(code):
    global supabase
    if not supabase:
        supabase = connect_supabase()
        if not supabase:
            return False
    try:
        cleaned_code = code.strip()
        now = datetime.now()
        today = now.date().isoformat()

        # ── Step 1: find the reservation that matches this QR code and today ──
        res = (
            supabase
            .table(TABLE_NAME)
            .select("*")
            .eq(QR_COLUMN, cleaned_code)
            .eq(DATE_COLUMN, today)
            .execute()
        )
        if not res.data:
            print("⛔ No reservation found for today.")
            return False

        reservation = res.data[0]
        conf_number = reservation.get(CONF_NUMBER_COLUMN, "")

        # ── Step 2: extract base confirmation number (INR-00001 from INR-00001-2) ──
        # Split on the LAST dash only to isolate the slot suffix
        parts = conf_number.rsplit("-", 1)
        base_conf = parts[0] if len(parts) == 2 and parts[1].isdigit() else conf_number

        # ── Step 3: fetch ALL slots that share this base confirmation number today ──
        all_slots = (
            supabase
            .table(TABLE_NAME)
            .select(f"{START_TIME_COLUMN},{END_TIME_COLUMN}")
            .like(CONF_NUMBER_COLUMN, f"{base_conf}-%")
            .eq(DATE_COLUMN, today)
            .execute()
        )
        if not all_slots.data:
            # Fallback: use the single reservation we already found
            all_slots_data = [reservation]
        else:
            all_slots_data = all_slots.data

        # ── Step 4: determine earliest start and latest end across all slots ──
        start_times = [
            _parse_time(s[START_TIME_COLUMN])
            for s in all_slots_data
            if s.get(START_TIME_COLUMN)
        ]
        end_times = [
            _parse_time(s[END_TIME_COLUMN])
            for s in all_slots_data
            if s.get(END_TIME_COLUMN)
        ]

        if not start_times or not end_times:
            print("⛔ Reservation is missing time data.")
            return False

        earliest_start = min(start_times)
        latest_end = max(end_times)

        # ── Step 5: build the ±1-hour scannable window ──
        base_dt = datetime.combine(now.date(), earliest_start)
        window_open  = (base_dt - timedelta(hours=ACCESS_WINDOW_HOURS)).time()
        window_close = (datetime.combine(now.date(), latest_end) + timedelta(hours=ACCESS_WINDOW_HOURS)).time()
        current_time = now.time().replace(microsecond=0)

        in_window = window_open <= current_time <= window_close
        if not in_window:
            print(
                f"⛔ Outside scan window. Allowed: "
                f"{window_open.strftime('%H:%M')} – {window_close.strftime('%H:%M')}, "
                f"current: {current_time.strftime('%H:%M')}"
            )
        return in_window

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
