#!/usr/bin/env python3
"""
360安全卫士 sweeper .dat 文件解密脚本

算法 (从 SysSweeper.dll 0x1006cd95 逆向得到):
  自同步流密码:
    key = initial_key (单字节)
    for each byte:
        plaintext[i] = ciphertext[i] ^ key
        key = (key + plaintext[i] + 1) & 0xFF

该算法用于 tracesweeper.dat (key=0x23)，解密后为 GBK 编码的 INI 格式。
SysSweeperNew.dat 使用了不同的加密算法，本脚本无法解密它。

用法:
    python3 decrypt_syssweeper.py tracesweeper.dat
    python3 decrypt_syssweeper.py tracesweeper.dat -o out.ini -k 0x23
"""

import argparse
import sys

def decrypt_stream(data: bytes, key: int) -> bytes:
    """360 stream cipher decryption"""
    out = bytearray(len(data))
    dl = key & 0xFF
    for i, b in enumerate(data):
        pt = b ^ dl
        out[i] = pt
        dl = (dl + pt + 1) & 0xFF
    return bytes(out)

def encrypt_stream(data: bytes, key: int) -> bytes:
    """360 stream cipher encryption (inverse)"""
    out = bytearray(len(data))
    dl = key & 0xFF
    # Encryption: ct[i] = pt[i] ^ key; key = (key + pt[i] + 1) & 0xFF
    # (from SysSweeper.dll 0x1006cd38)
    for i, b in enumerate(data):
        out[i] = b ^ dl
        dl = (dl + b + 1) & 0xFF
    return bytes(out)

def main():
    p = argparse.ArgumentParser(description='Decrypt 360 sweeper .dat files')
    p.add_argument('input', help='Input .dat file')
    p.add_argument('-o', '--output', help='Output file (default: <input>.dec)')
    p.add_argument('-k', '--key', default='0x23', help='Initial key (default: 0x23)')
    p.add_argument('--hex-input', action='store_true', help='Input is hex-encoded (for WhiteList.dat)')
    args = p.parse_args()

    key = int(args.key, 0)
    
    with open(args.input, 'rb') as f:
        data = f.read()
    
    if args.hex_input:
        data = bytes.fromhex(data.strip().decode('ascii'))
    
    dec = decrypt_stream(data, key)
    
    out_path = args.output or (args.input + '.dec')
    with open(out_path, 'wb') as f:
        f.write(dec)
    
    print(f"Decrypted {len(data)} bytes with key 0x{key:02x} -> {out_path}")
    print(f"First 100 bytes: {dec[:100]}")

if __name__ == '__main__':
    main()
