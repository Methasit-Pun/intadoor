# How to Run the Door Control System

## Quick Start Guide

### 1. Install Dependencies
On your Raspberry Pi, run:
```bash
pip install supabase python-dotenv
```

### 2. Run the Program
```bash
cd /path/to/intadoor
python3 simple_door_control.py
```

### 3. Test QR Codes
When the program starts, you'll see:
```
=== Door Control System Started ===
Paste QR codes in the terminal to check access
Type 'quit' to exit
========================================
✓ Connected to Supabase database

Paste QR code here (or 'quit' to exit):
```

### 4. How to Use
1. **Paste QR Code**: Copy any text and paste it into the terminal
2. **System Response**: 
   - If QR code exists in database: `🟢 ACCESS GRANTED` → Door opens
   - If QR code not found: `🔴 ACCESS DENIED`
3. **Exit**: Type 'quit' to stop the program

## Example Session
```
Paste QR code here (or 'quit' to exit): https://example.com/qr/12345

==================================================
Checking QR code: https://example.com/qr/12345
✓ QR code found in reservations!
  Guest: John Doe
  Reservation ID: 1
🟢 ACCESS GRANTED
🚪 OPENING DOOR for 5 seconds...
  Door open... 5 seconds remaining
  Door open... 4 seconds remaining
  Door open... 3 seconds remaining
  Door open... 2 seconds remaining
  Door open... 1 seconds remaining
🔒 Door closed
==================================================

Paste QR code here (or 'quit' to exit): invalid_code

==================================================
Checking QR code: invalid_code
✗ QR code NOT found in reservations
🔴 ACCESS DENIED
QR code not found in reservations database
==================================================
```

## Testing on Windows (Development)
If testing on Windows before deploying to Raspberry Pi:
```bash
cd c:\Users\Asus\Desktop\intadoor
pip install supabase python-dotenv
python simple_door_control.py
```
*Note: GPIO will run in simulation mode on Windows*

## Automatic Startup (Raspberry Pi)
To run automatically on boot, create a systemd service:

1. Copy the service file:
```bash
sudo cp door-control.service /etc/systemd/system/
```

2. Enable auto-start:
```bash
sudo systemctl enable door-control.service
sudo systemctl start door-control.service
```

3. Check status:
```bash
sudo systemctl status door-control.service
```

## Troubleshooting

### "Supabase connection failed"
- Check your `.env` file has correct SUPABASE_URL and SUPABASE_ANON_KEY
- Verify internet connection
- Test database connection in Supabase dashboard

### "GPIO permission denied" 
- Run with sudo: `sudo python3 simple_door_control.py`
- Or add user to gpio group: `sudo usermod -a -G gpio $USER`

### "Table 'reservations' doesn't exist"
- Create the table in Supabase dashboard
- Run the SQL commands from README.md

## Log Files
- System logs: `door_system.log`
- Access attempts: Check `access_logs` table in Supabase
