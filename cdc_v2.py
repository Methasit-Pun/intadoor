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
