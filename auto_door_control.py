#!/usr/bin/env python3
"""
Optimized Automatic Door Control System
Auto-detects QR codes pasted directly in terminal
"""

import os
import sys
import time
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# GPIO setup
try:
    import RPi.GPIO as GPIO
    RASPBERRY_PI = True
except ImportError:
    RASPBERRY_PI = False

# Supabase setup
try:
    from supabase import create_client, Client
except ImportError:
    print("❌ Run: pip install supabase")
    sys.exit(1)

class AutoDoorController:
    def __init__(self):
        self.RELAY_PIN = 17
        self.door_open_duration = 10
        self.running = True
        self.last_qr = ""
        self.last_time = 0
        
        # Setup
        self._setup_gpio()
        self._setup_supabase()
        
        print("🚪 Auto Door Control Started")
        print("📱 Paste QR codes - they auto-process!")
        print("💡 Type 'quit' to exit\n")
    
    def _setup_gpio(self):
        if RASPBERRY_PI:
            GPIO.cleanup()
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self.RELAY_PIN, GPIO.OUT, initial=GPIO.HIGH)
            print("✓ GPIO ready - Door LOCKED")
        else:
            print("✓ Simulation mode")
    
    def _setup_supabase(self):
        url = os.getenv('SUPABASE_URL')
        key = os.getenv('SUPABASE_ANON_KEY')
        if not url or not key:
            print("❌ Missing Supabase credentials in .env")
            sys.exit(1)
        
        self.supabase = create_client(url, key)
        print("✓ Connected to database")
    
    def check_qr(self, qr_code):
        """Check QR code in database"""
        try:
            qr_code = qr_code.strip()
            if not qr_code:
                return False
            
            print(f"🔍 Checking: {qr_code}")
            
            response = self.supabase.table('reservations').select("*").eq('qr_code_url', qr_code).execute()
            
            if response.data:
                print("✅ QR code found!")
                if 'id' in response.data[0]:
                    print(f"   ID: {response.data[0]['id']}")
                return True
            else:
                print("❌ QR code NOT found")
                return False
                
        except Exception as e:
            print(f"💥 Database error: {e}")
            return False
    
    def open_door(self):
        """Open door for 10 seconds"""
        try:
            print(f"🔓 UNLOCKING DOOR for {self.door_open_duration} seconds...")
            
            # UNLOCK immediately
            if RASPBERRY_PI:
                GPIO.output(self.RELAY_PIN, GPIO.LOW)
            
            print("🚪 DOOR IS OPEN!")
            
            # Countdown
            for i in range(self.door_open_duration, 0, -1):
                print(f"   ⏰ {i} seconds remaining")
                time.sleep(1)
            
            # LOCK again
            if RASPBERRY_PI:
                GPIO.output(self.RELAY_PIN, GPIO.HIGH)
            
            print("🔒 Door LOCKED\n")
            
        except Exception as e:
            print(f"💥 Door error: {e}")
            if RASPBERRY_PI:
                GPIO.output(self.RELAY_PIN, GPIO.HIGH)
    
    def process_qr(self, qr_input):
        """Process QR code"""
        current_time = time.time()
        
        # Prevent duplicate processing
        if qr_input == self.last_qr and current_time - self.last_time < 3:
            return
        
        self.last_qr = qr_input
        self.last_time = current_time
        
        print("\n" + "="*40)
        
        if self.check_qr(qr_input):
            print("🟢 ACCESS GRANTED")
            self.open_door()
        else:
            print("🔴 ACCESS DENIED\n")
        
        print("📱 Ready for next QR code...")
    
    def auto_input_monitor(self):
        """Monitor terminal input automatically"""
        print("⌨️ Terminal monitor active...")
        
        while self.running:
            try:
                # Simple input with immediate processing
                user_input = input("").strip()
                
                if user_input.lower() in ['quit', 'exit', 'q']:
                    self.running = False
                    break
                
                if user_input and len(user_input) > 3:
                    # Auto-process any input longer than 3 characters
                    self.process_qr(user_input)
                
            except KeyboardInterrupt:
                self.running = False
                break
            except EOFError:
                self.running = False
                break
            except Exception as e:
                print(f"Input error: {e}")
    
    def run(self):
        """Main loop"""
        try:
            self.auto_input_monitor()
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Cleanup"""
        self.running = False
        if RASPBERRY_PI:
            GPIO.cleanup()
        print("✅ System shutdown")

def main():
    if not os.path.exists('.env'):
        print("❌ .env file not found!")
        sys.exit(1)
    
    controller = AutoDoorController()
    controller.run()

if __name__ == "__main__":
    main()
