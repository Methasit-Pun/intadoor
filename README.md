# IntaDoor v2

Raspberry Pi Door Control System with Web Interface and Local Authorization.

## Quick Start (Local)

1. **Install Dependencies**:
   ```bash
   pip install flask python-dotenv supabase
   ```
2. **Sync to Pi**:
   ```bash
   ./sync-up.sh
   ```

## Installation (On Raspberry Pi)

1. **Navigate to the directory**:
   ```bash
   cd ~/Desktop/intadoor
   ```
2. **Install as Service**:
   ```bash
   chmod +x install_service.sh
   ./install_service.sh
   ```

## Usage

- **Web Interface**: Open `http://<pi-ip-address>:9999`
- **Features**: 
  - Gigantic **OPEN DOOR** button (timed).
  - **Manual Stay Open** toggle.
  - **Simulate QR Scan** field for non-keyboard input.
- **Local Bypass**: The code `INR012603301800000871` is hardcoded to work offline.

## Development Scripts

- `sync-up.sh`: Push local changes to Pi.
- `sync-down.sh`: Pull remote changes from Pi.
- `cdc_v2.py`: Main application logic.
