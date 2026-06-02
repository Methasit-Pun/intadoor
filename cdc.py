#!/usr/bin/env python3
"""
Raspberry Pi Door Control System - Web Version
Modified to include a web interface and local authorization.
"""

import os
import sys
import time
import logging
from datetime import datetime
import threading
import queue
from flask import Flask, render_template_string, request, jsonify

# Mock GPIO if not on Raspberry Pi
try:
    import RPi.GPIO as GPIO
except ImportError:
    class MockGPIO:
        BCM = 'BCM'
        OUT = 'OUT'
        LOW = 'LOW'
        HIGH = 'HIGH'
        def setmode(self, mode): pass
        def setup(self, pin, mode, initial=None): pass
        def output(self, pin, value): pass
        def cleanup(self): pass
    GPIO = MockGPIO()
    print("WARNING: RPi.GPIO not found. Using Mock GPIO.")

from supabase import create_client, Client
from dotenv import load_dotenv

try:
    import evdev
except ImportError:
    evdev = None
    print("WARNING: evdev library not found. Hardware scanner will not function. Run: pip install evdev")

# Standard US Keyboard Mapping for alphanumeric QR codes
SCANCODES = {
    2: ('1', '!'), 3: ('2', '@'), 4: ('3', '#'), 5: ('4', '$'),
    6: ('5', '%'), 7: ('6', '^'), 8: ('7', '&'), 9: ('8', '*'),
    10: ('9', '('), 11: ('0', ')'), 12: ('-', '_'), 13: ('=', '+'),
    16: ('q', 'Q'), 17: ('w', 'W'), 18: ('e', 'E'), 19: ('r', 'R'),
    20: ('t', 'T'), 21: ('y', 'Y'), 22: ('u', 'U'), 23: ('i', 'I'),
    24: ('o', 'O'), 25: ('p', 'P'), 26: ('[', '{'), 27: (']', '}'),
    30: ('a', 'A'), 31: ('s', 'S'), 32: ('d', 'D'), 33: ('f', 'F'),
    34: ('g', 'G'), 35: ('h', 'H'), 36: ('j', 'J'), 37: ('k', 'K'),
    38: ('l', 'L'), 39: (';', ':'), 40: ("'", '"'),
    44: ('z', 'Z'), 45: ('x', 'X'), 46: ('c', 'C'), 47: ('v', 'V'),
    48: ('b', 'B'), 49: ('n', 'N'), 50: ('m', 'M'), 51: (',', '<'),
    52: ('.', '>'), 53: ('/', '?'), 57: (' ', ' ')
}

class HardwareScanner(threading.Thread):
    def __init__(self, callback, device_name="YuRiot ScanCode Box"):
        """
        Background listener for a specific USB HID input device.
        :param callback: Function to call when an ENTER scancode completes a string.
        :param device_name: Exact or partial name of the device in /dev/input
        """
        super().__init__(daemon=True)
        self.callback = callback
        self.device_name = device_name
        self.device = None
        self._stop_event = threading.Event()
        self.buffer = []
        self.shift_pressed = False

    def find_device(self):
        if not evdev:
            return None
        try:
            devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
            for dev in devices:
                if self.device_name in dev.name:
                    return dev
            return None
        except PermissionError:
            logger.error("Permission denied to read /dev/input/. User must be root or in the 'input' group.")
            logger.error("Run: sudo usermod -a -G input $USER && newgrp input")
            time.sleep(10) # Prevent rapid spam
            return None
        except Exception as e:
            logger.error(f"Error scanning devices: {e}")
            return None

    def cleanup_device(self):
        if self.device:
            try:
                self.device.ungrab()
                logger.info(f"Released exclusive grab on {self.device.name}")
            except Exception:
                pass
            try:
                self.device.close()
            except Exception:
                pass
            self.device = None

    def run(self):
        if not evdev:
            logger.warning("evdev module is missing. Scanner thread terminating.")
            return

        logger.info(f"Hardware scanner thread started, looking for '{self.device_name}'...")

        while not self._stop_event.is_set():
            if self.device is None:
                self.device = self.find_device()
                if self.device is None:
                    time.sleep(2)  # Retry connection
                    continue
                
                try:
                    self.device.grab()  # EXCLUSIVE INTERCEPTION
                    logger.info(f"SUCCESS: Exclusively grabbed device: {self.device.name} at {self.device.path}")
                    self.buffer = [] # Clear buffer on connect
                except IOError as e:
                    logger.error(f"Failed to grab device {self.device.name} (Is it already grabbed?): {e}")
                    self.device = None
                    time.sleep(2)
                    continue

            try:
                # Read hardware events bypassing OS keyboard buffers
                for event in self.device.read_loop():
                    if self._stop_event.is_set():
                        break

                    if event.type == evdev.ecodes.EV_KEY:
                        key_event = evdev.categorize(event)
                        
                        # Monitor Shift Keys state
                        if key_event.scancode in [evdev.ecodes.KEY_LEFTSHIFT, evdev.ecodes.KEY_RIGHTSHIFT]:
                            if key_event.keystate == key_event.key_down:
                                self.shift_pressed = True
                            elif key_event.keystate == key_event.key_up:
                                self.shift_pressed = False
                            continue

                        # Process Key Down events
                        if key_event.keystate == key_event.key_down:
                            if key_event.scancode == evdev.ecodes.KEY_ENTER:
                                # Trigger callback and clear buffer
                                final_string = "".join(self.buffer)
                                logger.info(f"Scanned sequence captured: {final_string}")
                                if final_string:
                                    try:
                                        self.callback(final_string)
                                    except Exception as e:
                                        logger.error(f"Callback error: {e}")
                                self.buffer = []
                            elif key_event.scancode in SCANCODES:
                                # Append mapped character
                                char_tuple = SCANCODES[key_event.scancode]
                                char = char_tuple[1] if self.shift_pressed else char_tuple[0]
                                self.buffer.append(char)
                                
            except (IOError, evdev.device.EvdevError) as e:
                logger.warning(f"Device disconnected or read error: {e}")
                self.cleanup_device()

    def stop(self):
        self._stop_event.set()
        self.cleanup_device()

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('door_system_web.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class DoorController:
    def __init__(self):
        # GPIO Configuration
        self.RELAY_PIN = 17  # GPIO pin for relay control
        self.door_open_duration = 5  # seconds
        
        # Local authorized codes
        self.local_authorized_codes = [
            "INR012603301800000871"
        ]

        # Supabase configuration
        self.supabase_url = os.getenv('SUPABASE_URL')
        self.supabase_key = os.getenv('SUPABASE_ANON_KEY')
        self.table_name = os.getenv('SUPABASE_TABLE', 'reservations')
        self.qr_column = 'qr_code_url'

        # State
        self.is_manually_open = False
        self.lock = threading.Lock()

        # Initialize Hardware Scanner
        self.scanner = HardwareScanner(callback=self.process_qr_scan)
        self.scanner.start()

        # Initialize components
        self._setup_gpio()
        try:
            self._setup_supabase()
        except Exception as e:
            logger.warning(f"Supabase setup failed (using local mode): {e}")
            self.supabase = None

        logger.info("Door control system (Web Version) initialized")

    def _setup_gpio(self):
        try:
            GPIO.cleanup()
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self.RELAY_PIN, GPIO.OUT, initial=GPIO.LOW)
            logger.info(f"GPIO initialized - Relay pin {self.RELAY_PIN}")
        except Exception as e:
            logger.error(f"Failed to setup GPIO: {e}")

    def _setup_supabase(self):
        if not self.supabase_url or not self.supabase_key:
            return
        self.supabase: Client = create_client(self.supabase_url, self.supabase_key)
        logger.info("Supabase client initialized")

    def check_code(self, code):
        code = code.strip()
        if not code: return False

        # 1. Check local codes
        if code in self.local_authorized_codes:
            logger.info(f"QR code '{code}' authorized locally")
            return True

        # 2. Check Database
        if self.supabase:
            try:
                response = self.supabase.table(self.table_name).select("*").eq(self.qr_column, code).execute()
                if response.data:
                    logger.info(f"QR code '{code}' authorized via database")
                    return True
            except Exception as e:
                logger.error(f"Database error: {e}")
        
        return False

    def set_door_state(self, open_state):
        """Hardware control for door state"""
        with self.lock:
            if open_state:
                GPIO.output(self.RELAY_PIN, GPIO.HIGH)
                logger.info("Relay HIGH - Door Unlocked")
            else:
                GPIO.output(self.RELAY_PIN, GPIO.LOW)
                logger.info("Relay LOW - Door Locked")

    def open_door_timed(self):
        """Temporary open"""
        if self.is_manually_open:
            return # Already open
            
        self.set_door_state(True)
        time.sleep(self.door_open_duration)
        
        # Only lock if we haven't switched to manual open in the meantime
        if not self.is_manually_open:
            self.set_door_state(False)

    def process_qr_scan(self, code):
        logger.info(f"Processing scan: {code}")
        if self.check_code(code):
            threading.Thread(target=self.open_door_timed).start()
            self.log_access(code, True)
            return True
        else:
            self.log_access(code, False)
            return False

    def log_access(self, qr_code, success):
        if not self.supabase: return
        try:
            access_log = {
                "qr_code_url": qr_code,
                "timestamp": datetime.now().isoformat(),
                "success": success,
                "device": os.getenv('DEVICE_NAME', 'web_pi_door'),
                "access_type": "web_or_qr"
            }
            self.supabase.table("access_logs").insert(access_log).execute()
        except Exception as e:
            logger.error(f"Log error: {e}")

    def cleanup(self):
        self.set_door_state(False)
        GPIO.cleanup()

# --- Web Server ---
app = Flask(__name__)
controller = DoorController()

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Door Control</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: sans-serif; text-align: center; padding: 20px; background: #f0f0f0; }
        .btn-big { 
            padding: 40px; font-size: 30px; width: 80%; max-width: 400px;
            background: #e74c3c; color: white; border: none; border-radius: 20px;
            box-shadow: 0 10px #c0392b; cursor: pointer; margin: 20px;
        }
        .btn-big:active { box-shadow: 0 5px #c0392b; transform: translateY(5px); }
        .switch-container { margin: 30px; font-size: 20px; }
        .switch { position: relative; display: inline-block; width: 60px; height: 34px; }
        .switch input { opacity: 0; width: 0; height: 0; }
        .slider { position: absolute; cursor: pointer; top: 0; left: 0; right: 0; bottom: 0; background-color: #ccc; transition: .4s; border-radius: 34px; }
        .slider:before { position: absolute; content: ""; height: 26px; width: 26px; left: 4px; bottom: 4px; background-color: white; transition: .4s; border-radius: 50%; }
        input:checked + .slider { background-color: #2ecc71; }
        input:checked + .slider:before { transform: translateX(26px); }
        .qr-input { padding: 10px; font-size: 18px; width: 80%; max-width: 300px; margin-top: 20px; }
        #status { margin-top: 20px; font-weight: bold; }
    </style>
</head>
<body>
    <h1>Door Control System</h1>
    
    <button class="btn-big" onclick="action('open_timed')">OPEN DOOR</button>
    
    <div class="switch-container">
        <label>Manual Stay Open: </label>
        <label class="switch">
            <input type="checkbox" id="toggle" onchange="toggleManual(this.checked)">
            <span class="slider"></span>
        </label>
    </div>

    <hr>
    <h3>Simulate QR Scan</h3>
    <input type="text" id="qr_input" class="qr-input" placeholder="Enter QR code...">
    <button onclick="scanQR()" style="padding: 10px 20px; font-size: 18px;">Scan</button>

    <div id="status"></div>

    <script>
        function action(cmd) {
            fetch('/action/' + cmd).then(r => r.json()).then(data => {
                document.getElementById('status').innerText = data.message;
                setTimeout(() => document.getElementById('status').innerText = '', 3000);
            });
        }
        
        function toggleManual(state) {
            fetch('/toggle?state=' + state).then(r => r.json());
        }

        function scanQR() {
            let code = document.getElementById('qr_input').value;
            fetch('/scan?code=' + encodeURIComponent(code)).then(r => r.json()).then(data => {
                document.getElementById('status').innerText = data.success ? "✓ Access Granted" : "✗ Access Denied";
                document.getElementById('qr_input').value = '';
            });
        }
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/action/<cmd>')
def handle_action(cmd):
    if cmd == 'open_timed':
        threading.Thread(target=controller.open_door_timed).start()
        return jsonify({"status": "ok", "message": "Opening door..."})
    return jsonify({"status": "error"})

@app.route('/toggle')
def handle_toggle():
    state = request.args.get('state') == 'true'
    controller.is_manually_open = state
    controller.set_door_state(state)
    return jsonify({"status": "ok", "state": state})

@app.route('/scan')
def handle_scan():
    code = request.args.get('code', '')
    success = controller.process_qr_scan(code)
    return jsonify({"status": "ok", "success": success})

if __name__ == "__main__":
    try:
        # Run Flask in a way that doesn't block if needed, 
        # but for this script it's the main event.
        app.run(host='0.0.0.0', port=9999)
    finally:
        controller.cleanup()
