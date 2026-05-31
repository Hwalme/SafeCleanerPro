import os
import sys
import base64
from Crypto.PublicKey import RSA
from Crypto.Signature import pkcs1_15
from Crypto.Hash import SHA256

def generate_license(hwid, private_key_path):
    if not os.path.exists(private_key_path):
        print(f"❌ Error: Private key not found at {private_key_path}")
        print("Please run generate_keys.py first.")
        sys.exit(1)
        
    # Load private key
    with open(private_key_path, 'rb') as f:
        private_key = RSA.import_key(f.read())
        
    # Hash the HWID
    h = SHA256.new(hwid.encode('utf-8'))
    
    # Sign the hash
    signature = pkcs1_15.new(private_key).sign(h)
    
    # Encode to base64 to make it a printable license string
    license_key = base64.b64encode(signature).decode('utf-8')
    return license_key

if __name__ == "__main__":
    print("========================================")
    print("  SafeCleaner Pro - License Generator   ")
    print("========================================")
    hwid = input("Enter Customer Hardware ID (HWID): ").strip()
    
    if not hwid:
        print("HWID cannot be empty.")
        sys.exit(1)
        
    current_dir = os.path.dirname(os.path.abspath(__file__))
    private_key_path = os.path.join(os.path.dirname(current_dir), 'keys', 'private.pem')
    
    license_key = generate_license(hwid, private_key_path)
    
    print("\n✅ License Key Generated Successfully!\n")
    print("Provide this key to the customer:")
    print("-" * 50)
    print(license_key)
    print("-" * 50)
