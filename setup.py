#!/usr/bin/env python3
"""
Installation and setup script for Raspberry Pi Door Control System
"""

import os
import sys
import subprocess
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def check_raspberry_pi():
    """Check if running on Raspberry Pi"""
    try:
        with open('/proc/cpuinfo', 'r') as f:
            cpuinfo = f.read()
        return 'BCM' in cpuinfo or 'Raspberry Pi' in cpuinfo
    except:
        return False

def install_packages():
    """Install required Python packages"""
    logger.info("Installing required packages...")
    try:
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'])
        logger.info("Packages installed successfully")
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to install packages: {e}")
        return False
    return True

def setup_environment():
    """Setup environment file"""
    if not os.path.exists('.env'):
        if os.path.exists('.env.example'):
            logger.info("Creating .env file from template...")
            with open('.env.example', 'r') as src, open('.env', 'w') as dst:
                dst.write(src.read())
            logger.info("Please edit .env file with your Supabase credentials")
        else:
            logger.error(".env.example not found")
            return False
    else:
        logger.info(".env file already exists")
    return True

def setup_gpio_permissions():
    """Setup GPIO permissions for non-root user"""
    if check_raspberry_pi():
        logger.info("Setting up GPIO permissions...")
        try:
            # Add user to gpio group
            subprocess.run(['sudo', 'usermod', '-a', '-G', 'gpio', os.getenv('USER', 'pi')])
            logger.info("User added to gpio group. You may need to log out and back in.")
        except Exception as e:
            logger.warning(f"Could not set GPIO permissions: {e}")

def create_systemd_service():
    """Create systemd service for auto-start"""
    service_content = f"""[Unit]
Description=Door Control System
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory={os.getcwd()}
ExecStart=/usr/bin/python3 {os.path.join(os.getcwd(), 'door_control.py')}
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
"""
    
    service_path = '/etc/systemd/system/door-control.service'
    
    try:
        logger.info("Creating systemd service...")
        with open('door-control.service', 'w') as f:
            f.write(service_content)
        
        # Copy to systemd directory (requires sudo)
        subprocess.run(['sudo', 'cp', 'door-control.service', service_path])
        subprocess.run(['sudo', 'systemctl', 'daemon-reload'])
        
        logger.info("Systemd service created. To enable auto-start:")
        logger.info("sudo systemctl enable door-control.service")
        logger.info("sudo systemctl start door-control.service")
        
    except Exception as e:
        logger.warning(f"Could not create systemd service: {e}")

def main():
    logger.info("Setting up Raspberry Pi Door Control System...")
    
    # Check if running on Raspberry Pi
    if not check_raspberry_pi():
        logger.warning("This doesn't appear to be a Raspberry Pi. GPIO functionality may not work.")
    
    # Install packages
    if not install_packages():
        logger.error("Setup failed during package installation")
        sys.exit(1)
    
    # Setup environment
    if not setup_environment():
        logger.error("Setup failed during environment configuration")
        sys.exit(1)
    
    # Setup GPIO permissions
    setup_gpio_permissions()
    
    # Create systemd service
    create_systemd_service()
    
    logger.info("\nSetup completed! Next steps:")
    logger.info("1. Edit .env file with your Supabase credentials")
    logger.info("2. Create the required tables in Supabase (see README.md)")
    logger.info("3. Test the system: python3 door_control.py")
    logger.info("4. Optional: Enable auto-start with systemctl")

if __name__ == "__main__":
    main()
