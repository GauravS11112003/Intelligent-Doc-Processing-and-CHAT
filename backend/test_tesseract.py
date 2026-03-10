"""
Quick test script to verify Tesseract OCR installation.
Run: python test_tesseract.py
"""

import sys
from pathlib import Path
import pytesseract

# Same paths as in main.py
TESSERACT_PATHS = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    r"C:\Tesseract-OCR\tesseract.exe",
]


def test_tesseract():
    print("Testing Tesseract OCR installation...\n")
    
    # Try without setting path first
    try:
        version = pytesseract.get_tesseract_version()
        print(f"[OK] Tesseract found! Version: {version}")
        print(f"  Path: {pytesseract.pytesseract.tesseract_cmd}")
        return True
    except Exception as e:
        print(f"[FAIL] Tesseract not found in PATH: {e}\n")
        print("Trying common installation paths...\n")
    
    # Try common paths
    for path in TESSERACT_PATHS:
        if Path(path).exists():
            print(f"Found executable at: {path}")
            pytesseract.pytesseract.tesseract_cmd = path
            try:
                version = pytesseract.get_tesseract_version()
                print(f"[OK] Tesseract works! Version: {version}")
                return True
            except Exception as e:
                print(f"[FAIL] Failed to use {path}: {e}")
        else:
            print(f"[FAIL] Not found: {path}")
    
    print("\n" + "="*60)
    print("Tesseract OCR is NOT installed or not found.")
    print("\nTo install:")
    print("1. Download: https://digi.bib.uni-mannheim.de/tesseract/")
    print("2. Get: tesseract-ocr-w64-setup-5.5.0.20241111.exe")
    print("3. Install to: C:\\Program Files\\Tesseract-OCR\\")
    print("4. Restart your backend server")
    print("="*60)
    return False


if __name__ == "__main__":
    success = test_tesseract()
    sys.exit(0 if success else 1)
