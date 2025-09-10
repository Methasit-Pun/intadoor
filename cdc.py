#!/usr/bin/env python3
"""
Clipboard Monitor Door Control System
Automatically detects when QR codes are pasted and processes them immediately
No need to press Enter - just paste and it auto-processes
"""

import os
import sys
import time
import logging
import threading
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('door_system.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Import clipboard monitoring
try:
    import pyperclip
    CLIPBOARD_AVAILABLE = True
except ImportError:
    CLIPBOARD_AVAILABLE = False
    print("Installing pyperclip for clipboard monitoring...")
    os.system("pip install pyperclip")
    try:
        import pyperclip
        CLIPBOARD_AVAILABLE = True
    except ImportError:
        CLIPBOARD_AVAILABLE = False

# Only import GPIO if running on Raspberry Pi
try:
    import RPi.GPIO as GPIO
    RASPBERRY_PI = True
    logger.info("Running on Raspberry Pi - GPIO enabled")
except ImportError:
    RASPBERRY_PI = False
    logger.info("Not running on Raspberry Pi - GPIO simulation mode")

# Import Supabase
try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False
    logger.error("Supabase not installed. Run: pip install supabase")
    sys.exit(1)

class ClipboardDoorController:
    def __init__(self):
        # GPIO Configuration
        self.RELAY_PIN = 11  # GPIO pin for relay control
        self.door_open_duration = int(os.getenv('DOOR_OPEN_DURATION', 5))
        
        # Supabase configuration
        self.supabase_url = os.getenv('SUPABASE_URL')
        self.supabase_key = os.getenv('SUPABASE_ANON_KEY')
        self.table_name = os.getenv('SUPABASE_TABLE', 'reservations')
        self.qr_column = 'qr_code_url'
        
        # Clipboard monitoring
        self.last_clipboard_content = ""
        self.last_processed_code = ""
        self.last_process_time = 0
        self.min_interval = 2  # Minimum seconds between processing same code
        self.min_length = 3   # Minimum QR code length
        
        # Running flag
        self.running = True
        
        # Initialize components
        self._setup_gpio()
        self._setup_supabase()
        
        logger.info("Clipboard door control system initialized")
        print("=== Clipboard Monitor Door Control System ===")
        print("📋 Monitoring clipboard for QR codes")
        print("📱 Just copy/paste QR codes - they auto-process instantly!")
        print("⚡ No need to press Enter - automatic detection")
        print("💡 Press Ctrl+C to exit")
        print("="*50)
    
    def _setup_gpio(self):
        """Initialize GPIO settings for relay control"""
        if RASPBERRY_PI:
            try:
                GPIO.setmode(GPIO.BOARD)  # Use physical pin numbering
                GPIO.setup(self.RELAY_PIN, GPIO.OUT)
                GPIO.output(self.RELAY_PIN, GPIO.LOW)  # Door closed (relay off)
                logger.info(f"GPIO initialized - Relay pin {self.RELAY_PIN} set to LOW (door closed)")
            except Exception as e:
                logger.error(f"Failed to setup GPIO: {e}")
                raise
        else:
            logger.info("GPIO simulation mode - no actual GPIO control")
    
    def _setup_supabase(self):
        """Initialize Supabase client"""
        try:
            if not self.supabase_url or not self.supabase_key:
                raise ValueError("Supabase URL and key must be provided in .env file")
            
            self.supabase: Client = create_client(self.supabase_url, self.supabase_key)
            logger.info("Supabase client initialized successfully")
            print("✅ Connected to Supabase database")
        except Exception as e:
            logger.error(f"Failed to setup Supabase: {e}")
            print(f"❌ Failed to connect to Supabase: {e}")
            raise
    
    def check_qr_code_in_database(self, qr_code):
        """
        Check if the QR code exists in the reservations table
        
        Args:
            qr_code (str): The QR code content to verify
            
        Returns:
            bool: True if QR code is found, False otherwise
        """
        try:
            # Clean the input
            qr_code = qr_code.strip()
            
            if not qr_code:
                return False
            
            print(f"🔍 Checking QR code: {qr_code}")
            
            # Query the reservations table for the qr_code_url
            response = self.supabase.table(self.table_name).select("*").eq(self.qr_column, qr_code).execute()
            
            if response.data and len(response.data) > 0:
                reservation = response.data[0]
                print(f"✅ QR code found in reservations!")
                logger.info(f"QR code '{qr_code}' found - Access granted")
                if 'guest_name' in reservation:
                    print(f"   👤 Guest: {reservation['guest_name']}")
                if 'id' in reservation:
                    print(f"   🆔 Reservation ID: {reservation['id']}")
                return True
            else:
                print(f"❌ QR code NOT found in reservations")
                logger.warning(f"QR code '{qr_code}' not found - Access denied")
                return False
                
        except Exception as e:
            logger.error(f"Database query error: {e}")
            print(f"💥 ERROR: Database connection failed - {e}")
            return False
    
    def open_door(self):
        """Open the door by activating the relay"""
        try:
            print(f"🚪 OPENING DOOR for {self.door_open_duration} seconds...")
            
            if RASPBERRY_PI:
                GPIO.output(self.RELAY_PIN, GPIO.HIGH)  # Activate relay (open door)
                logger.info("Door relay activated")
            else:
                print("   [SIMULATION] Relay activated - door would open")
            
            # Countdown timer
            for i in range(self.door_open_duration, 0, -1):
                print(f"   🕐 Door open... {i} seconds remaining")
                time.sleep(1)
            
            # Close door
            if RASPBERRY_PI:
                GPIO.output(self.RELAY_PIN, GPIO.LOW)  # Deactivate relay (close door)
                logger.info("Door relay deactivated")
            else:
                print("   [SIMULATION] Relay deactivated - door would close")
            
            print("🔒 Door closed")
            
        except Exception as e:
            logger.error(f"Error controlling door: {e}")
            # Ensure door is closed in case of error
            if RASPBERRY_PI:
                GPIO.output(self.RELAY_PIN, GPIO.LOW)
            print(f"💥 ERROR: Door control failed - {e}")
    
    def log_access_attempt(self, qr_code, success):
        """Log access attempts to database"""
        try:
            access_log = {
                "qr_code_url": qr_code,
                "timestamp": datetime.now().isoformat(),
                "success": success,
                "device": os.getenv('DEVICE_NAME', 'raspberry_pi_door'),
                "access_type": "door_entry"
            }
            
            self.supabase.table("access_logs").insert(access_log).execute()
            logger.info(f"Access logged: {qr_code} - {'Success' if success else 'Failed'}")
            
        except Exception as e:
            logger.error(f"Failed to log access: {e}")
    
    def process_qr_input(self, qr_input):
        """Process QR code input and control door"""
        current_time = time.time()
        
        # Avoid processing the same code too frequently
        if (qr_input == self.last_processed_code and 
            current_time - self.last_process_time < self.min_interval):
            return
        
        self.last_processed_code = qr_input
        self.last_process_time = current_time
        
        print("\n" + "⚡" + "="*48 + "⚡")
        print(f"📋 Auto-detected QR Code: {qr_input}")
        
        # Check if QR code exists in database
        if self.check_qr_code_in_database(qr_input):
            print("🟢 ACCESS GRANTED")
            self.open_door()
            self.log_access_attempt(qr_input, True)
        else:
            print("🔴 ACCESS DENIED")
            print("❌ QR code not found in reservations database")
            self.log_access_attempt(qr_input, False)
        
        print("="*50)
        print("📋 Monitoring clipboard for next QR code...")
    
    def monitor_clipboard(self):
        """Monitor clipboard for new QR code content"""
        if not CLIPBOARD_AVAILABLE:
            print("❌ Clipboard monitoring not available. Install pyperclip.")
            return
        
        print("📋 Clipboard monitoring started...")
        print("📱 Copy any QR code to automatically process it!")
        
        while self.running:
            try:
                current_clipboard = pyperclip.paste()
                
                # Check if clipboard content has changed
                if (current_clipboard != self.last_clipboard_content and 
                    current_clipboard.strip() and 
                    len(current_clipboard.strip()) >= self.min_length):
                    
                    cleaned_content = current_clipboard.strip()
                    
                    # Avoid processing obvious non-QR content
                    if not any(skip in cleaned_content.lower() for skip in ['password', 'username', 'email']):
                        print(f"\n📥 New clipboard content detected!")
                        self.process_qr_input(cleaned_content)
                    
                    self.last_clipboard_content = current_clipboard
                
                time.sleep(0.5)  # Check clipboard every 500ms
                
            except KeyboardInterrupt:
                print("\n🛑 Clipboard monitoring stopped")
                self.running = False
                break
            except Exception as e:
                logger.error(f"Error monitoring clipboard: {e}")
                time.sleep(1)
    
    def run(self):
        """Main loop with clipboard monitoring"""
        try:
            if CLIPBOARD_AVAILABLE:
                self.monitor_clipboard()
            else:
                print("❌ Cannot monitor clipboard. Falling back to manual input.")
                print("Please install pyperclip: pip install pyperclip")
                
                while self.running:
                    try:
                        user_input = input("Paste QR code: ").strip()
                        if user_input.lower() in ['quit', 'exit', 'q']:
                            break
                        if len(user_input) > 0:
                            self.process_qr_input(user_input)
                    except KeyboardInterrupt:
                        break
        
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Clean up resources"""
        self.running = False
        try:
            if RASPBERRY_PI:
                GPIO.cleanup()
                logger.info("GPIO cleanup completed")
            print("✅ System shutdown complete")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

def main():
    """Main function"""
    try:
        # Check if .env file exists
        if not os.path.exists('.env'):
            print("💥 ERROR: .env file not found!")
            print("Please create .env file with your Supabase credentials")
            print("See .env.example for template")
            sys.exit(1)
        
        # Create and start door controller
        controller = ClipboardDoorController()
        controller.run()
        
    except Exception as e:
        logger.error(f"Failed to start system: {e}")
        print(f"💥 FATAL ERROR: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
