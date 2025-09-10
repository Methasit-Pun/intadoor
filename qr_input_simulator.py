#!/usr/bin/env python3
"""
QR Code Input Simulator
Simulates QR code scanner input by monitoring clipboard or using keyboard input
"""

import time
import logging
import pyperclip
from door_control import DoorController

logger = logging.getLogger(__name__)

class QRInputSimulator:
    def __init__(self, door_controller):
        self.door_controller = door_controller
        self.last_clipboard_content = ""
        
    def monitor_clipboard(self):
        """
        Monitor clipboard for new QR code content
        This simulates the QR scanner pasting content via mouse cursor
        """
        logger.info("Monitoring clipboard for QR code input...")
        
        while True:
            try:
                current_clipboard = pyperclip.paste()
                
                # Check if clipboard content has changed
                if current_clipboard != self.last_clipboard_content:
                    if current_clipboard.strip():  # Ignore empty clipboard
                        logger.info(f"New clipboard content detected: {current_clipboard}")
                        self.door_controller.process_input(current_clipboard)
                    
                    self.last_clipboard_content = current_clipboard
                
                time.sleep(0.5)  # Check clipboard every 500ms
                
            except KeyboardInterrupt:
                logger.info("Clipboard monitoring stopped")
                break
            except Exception as e:
                logger.error(f"Error monitoring clipboard: {e}")
                time.sleep(1)

def main():
    """Test the QR input simulator"""
    try:
        door_controller = DoorController()
        qr_simulator = QRInputSimulator(door_controller)
        qr_simulator.monitor_clipboard()
        
    except Exception as e:
        logger.error(f"Failed to start QR input simulator: {e}")

if __name__ == "__main__":
    main()
