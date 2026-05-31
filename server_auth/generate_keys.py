import os
from Crypto.PublicKey import RSA

def generate_keys(keys_dir):
    if not os.path.exists(keys_dir):
        os.makedirs(keys_dir)
        
    print(f"Generating 2048-bit RSA Key Pair in {keys_dir}...")
    key = RSA.generate(2048)
    
    # Save Private Key
    private_key_path = os.path.join(keys_dir, 'private.pem')
    with open(private_key_path, 'wb') as f:
        f.write(key.export_key('PEM'))
        
    # Save Public Key
    public_key_path = os.path.join(keys_dir, 'public.pem')
    with open(public_key_path, 'wb') as f:
        f.write(key.publickey().export_key('PEM'))
        
    print("✅ Keys generated successfully!")
    print(f"Private Key (KEEP SECRET): {private_key_path}")
    print(f"Public Key (DISTRIBUTE TO CLIENT): {public_key_path}")

if __name__ == "__main__":
    current_dir = os.path.dirname(os.path.abspath(__file__))
    keys_directory = os.path.join(os.path.dirname(current_dir), 'keys')
    generate_keys(keys_directory)
