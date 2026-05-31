import os
import winreg
import hashlib
import subprocess

def get_hwid_registry():
    """Query MachineGuid from registry (Instantaneous, <1ms, antivirus safe)."""
    try:
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE, 
            r"SOFTWARE\Microsoft\Cryptography", 
            0, 
            winreg.KEY_READ | winreg.KEY_WOW64_64KEY
        )
        guid, _ = winreg.QueryValueEx(key, "MachineGuid")
        winreg.CloseKey(key)
        if guid:
            hwid_hash = hashlib.md5(guid.encode('utf-8')).hexdigest().upper()
            return f"SCPRO-{hwid_hash[:8]}-{hwid_hash[8:16]}"
    except Exception:
        pass
    
    # Fallback to env variables (still no subprocess)
    comp_name = os.environ.get('COMPUTERNAME', 'HOST')
    proc_id = os.environ.get('PROCESSOR_IDENTIFIER', 'CPU')
    user_name = os.environ.get('USERNAME', 'USER')
    raw_id = f"{comp_name}-{proc_id}-{user_name}"
    hwid_hash = hashlib.md5(raw_id.encode('utf-8')).hexdigest().upper()
    return f"SCPRO-{hwid_hash[:8]}-{hwid_hash[8:16]}"

def get_hwid_wmic():
    """Retrieve motherboard/CPU serial using wmic (Legacy fallback for existing active buyers)."""
    try:
        board_cmd = subprocess.run(["wmic", "baseboard", "get", "serialnumber"], capture_output=True, text=True, timeout=5)
        board_serial = board_cmd.stdout.replace("SerialNumber", "").strip()
        
        cpu_cmd = subprocess.run(["wmic", "cpu", "get", "processorid"], capture_output=True, text=True, timeout=5)
        cpu_serial = cpu_cmd.stdout.replace("ProcessorId", "").strip()
        
        raw_id = f"{board_serial}-{cpu_serial}"
        hwid_hash = hashlib.md5(raw_id.encode('utf-8')).hexdigest().upper()
        return f"SCPRO-{hwid_hash[:8]}-{hwid_hash[8:16]}"
    except Exception:
        return "SCPRO-FALLBACK-HWID-0001"

def get_hwid():
    """Default HWID uses the fast registry-based method to avoid startup delay."""
    return get_hwid_registry()
