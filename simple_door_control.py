#!/usr/bin/env python3
"""
Simple Door Control System
Monitors terminal input for QR codes and checks with Supabase database
"""

import os
import sys
import time
import logging
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

class SimpleDoorController:
    def __init__(self):
        # GPIO Configuration
        self.RELAY_PIN = 17  # GPIO pin for relay control (BCM numbering)
        self.door_open_duration = int(os.getenv('DOOR_OPEN_DURATION', 5))
        
        # Supabase configuration
        self.supabase_url = os.getenv('SUPABASE_URL')
        self.supabase_key = os.getenv('SUPABASE_ANON_KEY')
        self.table_name = os.getenv('SUPABASE_TABLE', 'reservations')
        self.qr_column = 'qr_code_url'
        
        # Initialize components
        self._setup_gpio()
        self._setup_supabase()
        
        logger.info("Simple door control system initialized")
        print("=== Door Control System Started ===")
        print("Paste QR codes in the terminal to check access")
        print("Type 'quit' to exit")
        print("="*40)
    
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
                print("ERROR: Empty QR code provided")
                return False
            
            print(f"Checking QR code: {qr_code}")
            
            # Query the reservations table for the qr_code_url
            response = self.supabase.table(self.table_name).select("*").eq(self.qr_column, qr_code).execute()
            
            if response.data and len(response.data) > 0:
                reservation = response.data[0]
                print(f"✓ QR code found in reservations!")
                logger.info(f"QR code '{qr_code}' found - Access granted")
                if 'guest_name' in reservation:
                    print(f"  Guest: {reservation['guest_name']}")
                if 'id' in reservation:
                    print(f"  Reservation ID: {reservation['id']}")
                return True
            else:
                print(f"✗ QR code NOT found in reservations")
                logger.warning(f"QR code '{qr_code}' not found - Access denied")
                return False
                
        except Exception as e:
            logger.error(f"Database query error: {e}")
            print(f"ERROR: Database connection failed - {e}")
            return False
    
    def open_door(self):
        """Open the door by deactivating the relay (unlock)"""
        try:
            print(f"� UNLOCKING DOOR for {self.door_open_duration} seconds...")
            
            if RASPBERRY_PI:
                GPIO.output(self.RELAY_PIN, GPIO.LOW)  # Deactivate relay (unlock door)
                logger.info("Door relay deactivated - door unlocked")
            else:
                print("  [SIMULATION] Relay deactivated - door would unlock")
            
            # Countdown timer
            for i in range(self.door_open_duration, 0, -1):
                print(f"  Door unlocked... {i} seconds remaining")
                time.sleep(1)
            
            # Lock door again
            if RASPBERRY_PI:
                GPIO.output(self.RELAY_PIN, GPIO.HIGH)  # Activate relay (lock door)
                logger.info("Door relay activated - door locked")
            else:
                print("  [SIMULATION] Relay activated - door would lock")
            
            print("🔒 Door locked")
            
        except Exception as e:
            logger.error(f"Error controlling door: {e}")
            # Ensure door is locked in case of error
            if RASPBERRY_PI:
                GPIO.output(self.RELAY_PIN, GPIO.HIGH)
            print(f"ERROR: Door control failed - {e}")
    
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
        print("\n" + "="*50)
        
        # Check if QR code exists in database
        if self.check_qr_code_in_database(qr_input):
            print("🟢 ACCESS GRANTED")
            self.open_door()
            self.log_access_attempt(qr_input, True)
        else:
            print("🔴 ACCESS DENIED")
            print("QR code not found in reservations database")
            self.log_access_attempt(qr_input, False)
        
        print("="*50)
    
    def run(self):
        """Main loop to monitor for QR code input"""
        try:
            while True:
                try:
                    # Wait for QR code input
                    user_input = input("\nPaste QR code here (or 'quit' to exit): ").strip()
                    
                    if user_input.lower() in ['quit', 'exit', 'q']:
                        print("Shutting down door control system...")
                        break
                    
                    if user_input:
                        self.process_qr_input(user_input)
                    else:
                        print("Please paste a QR code")
                        
                except KeyboardInterrupt:
                    print("\nShutting down door control system...")
                    break
                except Exception as e:
                    logger.error(f"Error processing input: {e}")
                    print(f"Error: {e}")
        
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Clean up resources"""
        try:
            if RASPBERRY_PI:
                # Ensure door is locked before cleanup
                GPIO.output(self.RELAY_PIN, GPIO.HIGH)  # Lock door
                GPIO.cleanup()
                logger.info("GPIO cleanup completed - Door secured")
            print("System shutdown complete")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

def main():
    """Main function"""
    try:
        # Check if .env file exists
        if not os.path.exists('.env'):
            print("ERROR: .env file not found!")
            print("Please create .env file with your Supabase credentials")
            print("See .env.example for template")
            sys.exit(1)
        
        # Create and start door controller
        controller = SimpleDoorController()
        controller.run()
        
    except Exception as e:
        logger.error(f"Failed to start system: {e}")
        print(f"FATAL ERROR: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
