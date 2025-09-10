#!/usr/bin/env python3
"""
Raspberry Pi Door Control System
Monitors text input (from QR code scanner) and controls door relay
based on database verification through Supabase.
"""

import os
import sys
import time
import logging
from datetime import datetime
import RPi.GPIO as GPIO
from supabase import create_client, Client
from dotenv import load_dotenv
import threading
import queue

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

class DoorController:
    def __init__(self):
        # GPIO Configuration
        self.RELAY_PIN = 17  # GPIO pin for relay control (BCM numbering)
        self.door_open_duration = 5  # seconds to keep door open
        
        # Supabase configuration
        self.supabase_url = os.getenv('SUPABASE_URL')
        self.supabase_key = os.getenv('SUPABASE_ANON_KEY')
        self.table_name = os.getenv('SUPABASE_TABLE', 'reservations')
        self.qr_column = 'qr_code_url'
        
        # Input queue for processing QR codes
        self.input_queue = queue.Queue()
        
        # Initialize components
        self._setup_gpio()
        self._setup_supabase()
        
        logger.info("Door control system initialized")
    
    def _setup_gpio(self):
        """Initialize GPIO settings for relay control"""
        try:
            GPIO.cleanup()  # Clean up any previous GPIO usage
            GPIO.setmode(GPIO.BCM)  # Use BCM pin numbering (GPIO17)
            GPIO.setup(self.RELAY_PIN, GPIO.OUT, initial=GPIO.HIGH)  # Door locked (relay ON)
            logger.info(f"GPIO initialized - Relay pin {self.RELAY_PIN} set to HIGH (door locked)")
        except Exception as e:
            logger.error(f"Failed to setup GPIO: {e}")
            raise
    
    def _setup_supabase(self):
        """Initialize Supabase client"""
        try:
            if not self.supabase_url or not self.supabase_key:
                raise ValueError("Supabase URL and key must be provided in environment variables")
            
            self.supabase: Client = create_client(self.supabase_url, self.supabase_key)
            logger.info("Supabase client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to setup Supabase: {e}")
            raise
    
    def check_code_in_database(self, code):
        """
        Check if the scanned code exists in the reservations table qr_code_url column
        
        Args:
            code (str): The QR code content to verify
            
        Returns:
            bool: True if code is authorized, False otherwise
        """
        try:
            # Clean the input code
            code = code.strip()
            
            if not code:
                logger.warning("Empty code provided")
                return False
            
            # Query the reservations table for the qr_code_url
            response = self.supabase.table(self.table_name).select("*").eq(self.qr_column, code).execute()
            
            if response.data and len(response.data) > 0:
                reservation = response.data[0]
                logger.info(f"QR code '{code}' found in reservations - Access granted")
                logger.info(f"Reservation details: ID={reservation.get('id', 'N/A')}")
                return True
            else:
                logger.warning(f"QR code '{code}' not found in reservations - Access denied")
                print(f"ERROR: QR code not found in database. Access denied for: {code}")
                return False
                
        except Exception as e:
            logger.error(f"Database query error: {e}")
            print(f"ERROR: Database connection failed - {e}")
            return False
    
    def open_door(self):
        """Open the door by deactivating the relay (unlock)"""
        try:
            logger.info("Unlocking door...")
            GPIO.output(self.RELAY_PIN, GPIO.LOW)  # Deactivate relay (unlock door)
            
            # Keep door unlocked for specified duration
            time.sleep(self.door_open_duration)
            
            # Lock door again
            GPIO.output(self.RELAY_PIN, GPIO.HIGH)  # Activate relay (lock door)
            logger.info("Door locked again")
            
        except Exception as e:
            logger.error(f"Error controlling door: {e}")
            # Ensure door is locked in case of error
            GPIO.output(self.RELAY_PIN, GPIO.HIGH)
    
    def process_input(self, text_input):
        """
        Process text input from QR code scanner
        
        Args:
            text_input (str): The scanned QR code content
        """
        text_input = text_input.strip()
        
        if not text_input:
            logger.warning("Empty input received")
            print("ERROR: No QR code data received")
            return
        
        logger.info(f"Processing QR code input: {text_input}")
        print(f"Checking QR code: {text_input}")
        
        # Check if code is authorized in reservations table
        if self.check_code_in_database(text_input):
            print("✓ Access granted - Opening door...")
            self.open_door()
            # Log successful access
            self.log_access(text_input, True)
        else:
            print("✗ Access denied - QR code not found in reservations")
            logger.warning(f"Unauthorized access attempt with QR code: {text_input}")
            # Log failed access attempt
            self.log_access(text_input, False)
    
    def log_access(self, qr_code, success):
        """
        Log access attempts to database
        
        Args:
            qr_code (str): The QR code that was used
            success (bool): Whether access was granted
        """
        try:
            access_log = {
                "qr_code_url": qr_code,
                "timestamp": datetime.now().isoformat(),
                "success": success,
                "device": os.getenv('DEVICE_NAME', 'raspberry_pi_door'),
                "access_type": "door_entry"
            }
            
            # Insert into access log table (create this table in Supabase if needed)
            self.supabase.table("access_logs").insert(access_log).execute()
            logger.info(f"Access attempt logged: {qr_code} - {'Success' if success else 'Failed'}")
            
        except Exception as e:
            logger.error(f"Failed to log access attempt: {e}")
            # Don't fail the door operation if logging fails
    
    def input_listener(self):
        """
        Listen for text input (simulates QR code scanner input)
        This function runs in a separate thread
        """
        logger.info("Input listener started - waiting for QR codes...")
        
        while True:
            try:
                # In a real implementation, this would capture input from the QR scanner
                # For testing, we'll use standard input
                text_input = input("\nScan QR code (or type 'quit' to exit): ")
                
                if text_input.lower() == 'quit':
                    print("Shutting down door control system...")
                    break
                
                # Add input to queue for processing
                self.input_queue.put(text_input)
                
            except KeyboardInterrupt:
                logger.info("Input listener stopped by user")
                break
            except Exception as e:
                logger.error(f"Error in input listener: {e}")
    
    def start_processing(self):
        """Start the main processing loop"""
        logger.info("Starting door control system...")
        
        # Start input listener in a separate thread
        input_thread = threading.Thread(target=self.input_listener, daemon=True)
        input_thread.start()
        
        try:
            while True:
                try:
                    # Process queued inputs
                    if not self.input_queue.empty():
                        text_input = self.input_queue.get_nowait()
                        self.process_input(text_input)
                    
                    # Small delay to prevent excessive CPU usage
                    time.sleep(0.1)
                    
                except queue.Empty:
                    continue
                except KeyboardInterrupt:
                    logger.info("System stopped by user")
                    break
                except Exception as e:
                    logger.error(f"Error in main processing loop: {e}")
                    time.sleep(1)  # Wait before continuing
        
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Clean up GPIO and other resources"""
        try:
            # Ensure door is locked before cleanup
            GPIO.output(self.RELAY_PIN, GPIO.HIGH)  # Lock door
            GPIO.cleanup()
            logger.info("GPIO cleanup completed - Door secured")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

def main():
    """Main function to start the door control system"""
    try:
        door_controller = DoorController()
        door_controller.start_processing()
        
    except Exception as e:
        logger.error(f"Failed to start door control system: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
