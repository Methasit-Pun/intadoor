# 🚪 Raspberry Pi Door Control System

Automatic door control using QR codes and Supabase database verification.

## 🚀 Quick Start

1. **Install & Setup**
   ```bash
   pip install supabase python-dotenv pyperclip
   cp .env.example .env
   # Edit .env with your Supabase credentials
   ```

2. **Run System**
   ```bash
   python3 cdc.py    # Automatic clipboard monitoring
   python3 simple_door_control.py       # Manual input mode
   ```

3. **Use**: Copy/paste QR codes - they process automatically!

## 📋 Database Setup (Supabase)

**reservations table:**
```sql
CREATE TABLE reservations (
    id SERIAL PRIMARY KEY,
    qr_code_url VARCHAR(500) UNIQUE NOT NULL,
    guest_name VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW()
);
```

**access_logs table:**
```sql
CREATE TABLE access_logs (
    id SERIAL PRIMARY KEY,
    qr_code_url VARCHAR(500) NOT NULL,
    success BOOLEAN NOT NULL,
    timestamp TIMESTAMP DEFAULT NOW()
);
```

## ⚡ Hardware

- **GPIO Pin 11** → Relay signal
- **5V & GND** → Relay power
- **Relay NO** → Door lock (normally closed)

## 🎯 How It Works

1. **QR Detection** → Clipboard monitoring or manual input
2. **Database Check** → Query `reservations.qr_code_url`
3. **Door Action** → Open 5 seconds if QR found
4. **Logging** → Record all attempts

## 📁 Files

| File | Purpose |
|------|---------|
| `cdc.py` | 🔥 **Auto clipboard monitoring** |
| `simple_door_control.py` | Manual input mode |
| `auto_door_control.py` | Auto-process typed input |
| `.env` | Supabase credentials |

## 🛠️ Configuration

Edit `.env`:
```bash
SUPABASE_URL=your_project_url
SUPABASE_ANON_KEY=your_anon_key
SUPABASE_TABLE=reservations
DOOR_OPEN_DURATION=5
```

## 🔧 Troubleshooting

- **GPIO errors**: Run with `sudo`
- **Network issues**: Check Supabase credentials
- **No table**: Create database tables above
- **Logs**: Check `door_system.log`

## 💡 Usage Examples

**Automatic Mode** (Recommended):
```bash
python3 clipboard_door_control.py
# Just copy QR codes - they auto-process!
```

**Manual Mode**:
```bash
python3 simple_door_control.py
# Paste QR code: [enter QR here]
```

---

