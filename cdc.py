#!/usr/bin/env python3
import os, time, sys
import RPi.GPIO as GPIO
from supabase import create_client
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()

# ── Hardware ──────────────────────────────────────────────────────────────────
RELAY_PIN          = 17
DOOR_OPEN_DURATION = 6          # seconds

# ── Supabase ──────────────────────────────────────────────────────────────────
SUPABASE_URL  = os.getenv("SUPABASE_URL")
SUPABASE_KEY  = os.getenv("SUPABASE_ANON_KEY")
TABLE_NAME    = os.getenv("SUPABASE_TABLE", "reservations")
DEVICE_NAME   = os.getenv("DEVICE_NAME", "raspberry_pi_door")

# ── Table columns ─────────────────────────────────────────────────────────────
ACCESS_LOG_TABLE   = "access_logs"
QR_COLUMN          = "qr_code_url"
DATE_COLUMN        = "date"
START_TIME_COLUMN  = "start_time"
END_TIME_COLUMN    = "end_time"
CONF_NUMBER_COLUMN = "confirmation_number"

# ── Business rules ────────────────────────────────────────────────────────────
ACCESS_WINDOW_HOURS = 1         # scannable ± this many hours around the booking block
RECONNECT_INTERVAL  = 3600      # seconds between Supabase client refreshes

# Use a set for O(1) membership test
EMERGENCY_CODES = {
    "INR012509101700000201",
    "INR012508300900000131",
}

# ── Startup validation ────────────────────────────────────────────────────────
if not SUPABASE_URL or not SUPABASE_KEY:
    sys.exit("❌ SUPABASE_URL / SUPABASE_ANON_KEY are not set in .env — aborting.")

# ── GPIO setup ────────────────────────────────────────────────────────────────
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)
GPIO.setup(RELAY_PIN, GPIO.OUT, initial=GPIO.LOW)

# ── Supabase client ───────────────────────────────────────────────────────────
def connect_supabase():
    try:
        return create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        print(f"❌ Supabase init error: {e}", flush=True)
        return None

supabase = connect_supabase()
print("🚪 Door control system started.\n", flush=True)


def _get_supabase():
    """Return the active Supabase client, reconnecting once if it dropped."""
    global supabase
    if not supabase:
        supabase = connect_supabase()
    return supabase


# ── Helpers ───────────────────────────────────────────────────────────────────
def _parse_time(t_str: str):
    """Parse 'HH:MM:SS' or 'HH:MM' into a datetime.time object."""
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(t_str, fmt).time()
        except ValueError:
            pass
    raise ValueError(f"Unrecognised time format: {t_str!r}")


def open_door():
    try:
        print("🔓 Door unlocked", flush=True)
        GPIO.output(RELAY_PIN, GPIO.HIGH)
        time.sleep(DOOR_OPEN_DURATION)
        GPIO.output(RELAY_PIN, GPIO.LOW)
        print("🔒 Door locked again", flush=True)
    except Exception as e:
        print(f"⚠️ GPIO error: {e}", flush=True)
        # Full GPIO recovery
        GPIO.setwarnings(False)
        GPIO.cleanup()
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(RELAY_PIN, GPIO.OUT, initial=GPIO.LOW)


def check_code(code: str) -> bool:
    global supabase
    client = _get_supabase()
    if not client:
        return False
    try:
        now   = datetime.now()
        today = now.date().isoformat()

        # ── Step 1: look up this QR code for today (fetch only needed columns) ──
        res = (
            client.table(TABLE_NAME)
            .select(f"{CONF_NUMBER_COLUMN},{START_TIME_COLUMN},{END_TIME_COLUMN}")
            .eq(QR_COLUMN, code)
            .eq(DATE_COLUMN, today)
            .execute()
        )
        if not res.data:
            print("⛔ No reservation found for today.", flush=True)
            return False

        row         = res.data[0]
        conf_number = row.get(CONF_NUMBER_COLUMN, "")

        # ── Step 2: derive base confirmation number (INR-00001 from INR-00001-2) ──
        parts     = conf_number.rsplit("-", 1)
        base_conf = parts[0] if len(parts) == 2 and parts[1].isdigit() else conf_number

        # ── Step 3: fetch all sibling slots by base conf number ──
        slots_res = (
            client.table(TABLE_NAME)
            .select(f"{START_TIME_COLUMN},{END_TIME_COLUMN}")
            .like(CONF_NUMBER_COLUMN, f"{base_conf}-%")
            .eq(DATE_COLUMN, today)
            .execute()
        )
        slots = slots_res.data if slots_res.data else [row]

        # ── Step 4: find the overall booking window across all sibling slots ──
        start_times = [_parse_time(s[START_TIME_COLUMN]) for s in slots if s.get(START_TIME_COLUMN)]
        end_times   = [_parse_time(s[END_TIME_COLUMN])   for s in slots if s.get(END_TIME_COLUMN)]

        if not start_times or not end_times:
            print("⛔ Reservation is missing time data.", flush=True)
            return False

        today_dt     = now.date()
        window_open  = (datetime.combine(today_dt, min(start_times)) - timedelta(hours=ACCESS_WINDOW_HOURS)).time()
        window_close = (datetime.combine(today_dt, max(end_times))   + timedelta(hours=ACCESS_WINDOW_HOURS)).time()
        current_time = now.time().replace(microsecond=0)

        if not (window_open <= current_time <= window_close):
            print(
                f"⛔ Outside scan window. "
                f"Allowed: {window_open.strftime('%H:%M')} – {window_close.strftime('%H:%M')}, "
                f"now: {current_time.strftime('%H:%M')}",
                flush=True,
            )
            return False

        return True

    except Exception as e:
        print(f"❌ Database error: {e}", flush=True)
        supabase = None
        return False


def log_access(code: str, success: bool):
    client = _get_supabase()
    if not client:
        return
    try:
        client.table(ACCESS_LOG_TABLE).insert({
            "qr_code_url": code,
            "timestamp":   datetime.now().isoformat(),
            "success":     success,
            "device":      DEVICE_NAME,
            "access_type": "door_entry",
        }).execute()
    except Exception as e:
        print(f"⚠️ Log insert failed: {e}", flush=True)


# ── Main loop ─────────────────────────────────────────────────────────────────
last_reconnect = time.time()
try:
    while True:
        try:
            code = input("Scan QR code (or 'quit' to exit): ").strip()
        except EOFError:
            print("⚠️ Input stream closed, restarting...", flush=True)
            time.sleep(2)
            continue
        except Exception as e:
            print(f"⚠️ Input error: {e}", flush=True)
            time.sleep(2)
            continue

        if code.lower() == "quit":
            break

        if not code:
            print("⚠️ Empty input, try again.", flush=True)
            continue

        print("🔍 Checking code...", flush=True)
        authorized = code in EMERGENCY_CODES or check_code(code)
        if authorized:
            print("✅ Access granted", flush=True)
            open_door()
            log_access(code, True)
        else:
            print("❌ Access denied", flush=True)
            log_access(code, False)

        # Periodic Supabase client refresh
        if time.time() - last_reconnect >= RECONNECT_INTERVAL:
            supabase = connect_supabase()
            last_reconnect = time.time()

except KeyboardInterrupt:
    print("\n🛑 System stopped by user", flush=True)

finally:
    GPIO.output(RELAY_PIN, GPIO.LOW)
    GPIO.cleanup()
    print("GPIO cleaned up. Door locked.")
