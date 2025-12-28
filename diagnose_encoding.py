
import chardet
import os

path = 'app.py'

print(f"Checking encoding for {path}...")
try:
    with open(path, 'rb') as f:
        raw_data = f.read()
        result = chardet.detect(raw_data)
        print(f"Chardet result: {result}")
        
        # specific check for utf-16
        if b'\x00' in raw_data:
            print("Null bytes detected, possibly UTF-16 or UCS-2")
            
        try:
            content = raw_data.decode('utf-8')
            print("Successfully decoded as UTF-8")
        except UnicodeDecodeError:
            print("Failed to decode as UTF-8")
            
        try:
            content = raw_data.decode('cp950')
            print("Successfully decoded as CP950 (Big5)")
        except UnicodeDecodeError:
            print("Failed to decode as CP950")
            
        try:
            content = raw_data.decode('utf-16')
            print("Successfully decoded as UTF-16")
        except UnicodeDecodeError:
            print("Failed to decode as UTF-16")
            
except Exception as e:
    print(f"Error reading file: {e}")
