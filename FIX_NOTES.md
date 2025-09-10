Perfect! I've fixed the `EMERGENCY_CODE` attribute error and improved the logic for handling both emergency codes and internet connectivity issues. Here's what I've updated:

## ✅ **Fixed Issues:**

### **1. Emergency Code Handling:**
```python
# Fixed: Now uses self.EMERGENCY_CODES list instead of non-existent self.EMERGENCY_CODE
if qr_code in self.EMERGENCY_CODES:
    print(f"🔑 EMERGENCY CODE DETECTED: {qr_code}")
    return True
```

### **2. Improved Logic Flow:**
```python
def check_qr(self, qr_code):
    # FIRST: Check emergency codes (always work, no internet needed)
    if qr_code in self.EMERGENCY_CODES:
        return True
    
    # SECOND: Try database check (requires internet)
    try:
        response = self.supabase.table('reservations')...
        if response.data:
            return True  # Found in database
        else:
            print("❌ 404 QR code not found in database")
            return False
    except Exception:
        print("❌ 404 Internet connection error")
        return False
```

### **3. Clear Error Messages:**
- **Internet Issues**: `❌ 404 Internet connection error`
- **QR Not Found**: `❌ 404 QR code not found in database`
- **Emergency Codes**: `🔑 EMERGENCY CODE DETECTED`

## 🎯 **How It Works Now:**

### **With Internet Connection:**
1. **Emergency Code** → `🚨 EMERGENCY BYPASS MODE` → Door opens
2. **Valid QR** → `✅ QR code found in database` → Door opens  
3. **Invalid QR** → `❌ 404 QR code not found in database` → Access denied

### **Without Internet (Offline):**
1. **Emergency Code** → `🚨 EMERGENCY BYPASS MODE` → Door opens
2. **Any Other QR** → `❌ 404 Internet connection error` → Access denied

### **Emergency Codes That Always Work:**
- `"INR012509101700000201"` 
- `"INR012508300900000131"`

## 🚀 **Test Scenarios:**

```bash
# Test 1: Emergency code (works offline/online)
INR012509101700000201
> 🔑 EMERGENCY CODE DETECTED
> 🚨 EMERGENCY BYPASS MODE - Access granted!

# Test 2: Valid QR with internet
INR012507021300000011
> 🔍 Checking QR code in database
> ✅ QR code found in database!
> 🟢 ACCESS GRANTED

# Test 3: Invalid QR with internet
INVALID123
> 🔍 Checking QR code in database
> ❌ 404 QR code not found in database

# Test 4: Any QR without internet
ANYTHING
> 🔍 Checking QR code in database
> ❌ 404 Internet connection error
> 🌐 Database unavailable
```

The system now properly handles all conditions and the `EMERGENCY_CODE` attribute error is completely resolved! 🎉