#!/usr/bin/env python3
"""
Automatic Door Control System
Automatically processes QR codes without requiring Enter key
Monitors for text input and processes immediately when detected
"""

import os
import sys
import time
import logging
import threading
import queue
import select
from datetime import datetime
from dotenv import load_dotenv

# Try to import clipboard monitoring
try:
    import pyperclip
    CLIPBOARD_AVAILABLE = True
except ImportError:
    CLIPBOARD_AVAILABLE = False
    print("Installing pyperclip for automatic detection...")
    try:
        os.system("pip install pyperclip")
        import pyperclip
        CLIPBOARD_AVAILABLE = True
    except:
        CLIPBOARD_AVAILABLE = False

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

class AutomaticDoorController:
    def __init__(self):
        # GPIO Configuration
        self.RELAY_PIN = 17  # GPIO pin for relay control (BCM numbering)
        self.door_open_duration = 10  # 10 seconds to keep door unlocked
        
        # Supabase configuration
        self.supabase_url = os.getenv('SUPABASE_URL')
        self.supabase_key = os.getenv('SUPABASE_ANON_KEY')
        self.table_name = os.getenv('SUPABASE_TABLE', 'reservations')
        self.qr_column = 'qr_code_url'
        
        # Input processing
        self.input_queue = queue.Queue()
        self.last_processed_code = ""
        self.last_process_time = 0
        self.min_interval = 2  # Minimum seconds between processing same code
        self.last_clipboard_content = ""  # For clipboard monitoring
        
        # Running flag
        self.running = True
        
        # Initialize components
        self._setup_gpio()
        self._setup_supabase()
        
        logger.info("Automatic door control system initialized")
        print("=== Automatic Door Control System Started ===")
        print("🔄 Auto-processing mode: QR codes detected automatically")
        if CLIPBOARD_AVAILABLE:
            print("📋 Clipboard monitoring: Copy QR codes - they auto-process!")
        print("⌨️  Keyboard input: Type QR codes - they auto-process when you finish typing")
        print("💡 Type 'quit' to exit")
        print("="*65)
    
    def _setup_gpio(self):
        """Initialize GPIO settings for relay control"""
        if RASPBERRY_PI:
            try:
                GPIO.cleanup()  # Clean up any previous GPIO usage
                GPIO.setmode(GPIO.BCM)  # Use BCM pin numbering (GPIO17)
                GPIO.setup(self.RELAY_PIN, GPIO.OUT, initial=GPIO.HIGH)  # Door locked (relay ON)
                logger.info(f"GPIO initialized - Relay pin {self.RELAY_PIN} set to HIGH (door locked)")
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
            print("✓ Connected to Supabase database")
        except Exception as e:
            logger.error(f"Failed to setup Supabase: {e}")
            print(f"✗ Failed to connect to Supabase: {e}")
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
        """Unlock the door immediately for 10 seconds, then lock again"""
        try:
            print(f"� UNLOCKING DOOR immediately for {self.door_open_duration} seconds...")
            
            # UNLOCK the door immediately
            if RASPBERRY_PI:
                GPIO.output(self.RELAY_PIN, GPIO.LOW)  # Deactivate relay (UNLOCK door)
                logger.info("Door relay deactivated - DOOR UNLOCKED")
            else:
                print("   [SIMULATION] Relay deactivated - door UNLOCKED")
            
            print("🚪 DOOR IS NOW OPEN!")
            
            # Countdown timer while door is UNLOCKED
            for i in range(self.door_open_duration, 0, -1):
                print(f"   � Door UNLOCKED... {i} seconds remaining")
                time.sleep(1)
            
            # LOCK door again
            if RASPBERRY_PI:
                GPIO.output(self.RELAY_PIN, GPIO.HIGH)  # Activate relay (LOCK door)
                logger.info("Door relay activated - DOOR LOCKED")
            else:
                print("   [SIMULATION] Relay activated - door LOCKED")
            
            print("🔒 Door is now LOCKED again")
            
        except Exception as e:
            logger.error(f"Error controlling door: {e}")
            # Ensure door is LOCKED in case of error
            if RASPBERRY_PI:
                GPIO.output(self.RELAY_PIN, GPIO.HIGH)
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
        
        print("\n" + "🔄" + "="*48 + "🔄")
        print(f"📄 Processing QR Code: {qr_input}")
        
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
        print("📝 Ready for next QR code...")
    
    def monitor_clipboard(self):
        """Monitor clipboard for new QR code content"""
        if not CLIPBOARD_AVAILABLE:
            return
        
        print("📋 Clipboard monitoring started...")
        
        while self.running:
            try:
                current_clipboard = pyperclip.paste()
                
                # Check if clipboard content has changed
                if (current_clipboard != self.last_clipboard_content and 
                    current_clipboard.strip() and 
                    len(current_clipboard.strip()) >= 3):
                    
                    cleaned_content = current_clipboard.strip()
                    
                    # Avoid processing obvious non-QR content
                    if not any(skip in cleaned_content.lower() for skip in ['password', 'username', 'email']):
                        print(f"\n📥 Clipboard QR detected: {cleaned_content}")
                        self.input_queue.put(cleaned_content)
                    
                    self.last_clipboard_content = current_clipboard
                
                time.sleep(0.5)  # Check clipboard every 500ms
                
            except Exception as e:
                logger.error(f"Error monitoring clipboard: {e}")
                time.sleep(1)
    
    def auto_keyboard_monitor(self):
        """
        Monitor keyboard input with automatic processing
        """
        print("⌨️  Keyboard input monitor started...")
        print("💡 Type QR codes - they will process automatically when you pause typing")
        
        current_input = ""
        last_input_time = time.time()
        
        while self.running:
            try:
                # Non-blocking input check (Windows compatible)
                if sys.platform == "win32":
                    import msvcrt
                    while msvcrt.kbhit():
                        char = msvcrt.getch().decode('utf-8', errors='ignore')
                        if char == '\r' or char == '\n':  # Enter key
                            if current_input.strip():
                                if current_input.strip().lower() in ['quit', 'exit', 'q']:
                                    self.running = False
                                    return
                                print(f"\n⚡ Auto-processing: {current_input.strip()}")
                                self.input_queue.put(current_input.strip())
                                current_input = ""
                        elif char == '\b':  # Backspace
                            current_input = current_input[:-1]
                        elif char.isprintable():
                            current_input += char
                            last_input_time = time.time()
                            print(f"\r🔤 Typing: {current_input}", end="", flush=True)
                
                # Auto-process if user stops typing for 2 seconds
                if (current_input.strip() and 
                    time.time() - last_input_time > 2 and 
                    len(current_input.strip()) > 3):
                    
                    print(f"\n⚡ Auto-processing (timeout): {current_input.strip()}")
                    self.input_queue.put(current_input.strip())
                    current_input = ""
                
                time.sleep(0.1)
                
            except KeyboardInterrupt:
                self.running = False
                break
            except Exception as e:
                logger.error(f"Error in keyboard monitor: {e}")
                # Fallback to simple input
                try:
                    user_input = input("\nEnter QR code: ").strip()
                    if user_input.lower() in ['quit', 'exit', 'q']:
                        self.running = False
                        break
                    if user_input:
                        self.input_queue.put(user_input)
                except:
                    break
    
    def input_processor(self):
        """Process queued inputs automatically"""
        while self.running:
            try:
                if not self.input_queue.empty():
                    qr_input = self.input_queue.get_nowait()
                    self.process_qr_input(qr_input)
                else:
                    time.sleep(0.1)  # Small delay to prevent excessive CPU usage
            
            except queue.Empty:
                time.sleep(0.1)
            except Exception as e:
                logger.error(f"Error processing input: {e}")
    
    def run(self):
        """Main loop with automatic processing"""
        try:
            # Start input processor thread
            processor_thread = threading.Thread(target=self.input_processor, daemon=True)
            processor_thread.start()
            
            # Start clipboard monitor if available
            if CLIPBOARD_AVAILABLE:
                clipboard_thread = threading.Thread(target=self.monitor_clipboard, daemon=True)
                clipboard_thread.start()
            
            # Start keyboard monitor
            self.auto_keyboard_monitor()
        
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Clean up resources"""
        self.running = False
        try:
            if RASPBERRY_PI:
                # Ensure door is LOCKED before cleanup
                GPIO.output(self.RELAY_PIN, GPIO.HIGH)  # Lock door
                GPIO.cleanup()
                logger.info("GPIO cleanup completed - Door secured and locked")
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
        controller = AutomaticDoorController()
        controller.run()
        
    except Exception as e:
        logger.error(f"Failed to start system: {e}")
        print(f"💥 FATAL ERROR: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
