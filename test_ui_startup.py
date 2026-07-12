#!/usr/bin/env python3
"""Test UI startup."""
import sys
sys.path.insert(0, '.')
import os

print(f"Python: {sys.executable}")
print(f"CWD: {os.getcwd()}")

try:
    print("Importing PySide6...")
    from PySide6.QtWidgets import QApplication
    print("[OK] PySide6 available")
except ImportError as e:
    print(f"[FAIL] PySide6 not available: {e}")
    sys.exit(1)

try:
    print("Creating QApplication...")
    app = QApplication(sys.argv)
    print("[OK] QApplication created")
except Exception as e:
    print(f"[FAIL] QApplication creation failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

try:
    print("Importing UI...")
    from ui.aria_app import CognitiveOSUI
    print("[OK] UI imported")
    
    print("Creating UI window...")
    window = CognitiveOSUI()
    print("[OK] Window created")
    
    print("Showing window...")
    window.show()
    print("[OK] Window shown")
    
    print("Entering event loop (will run for 5 seconds)...")
    import time
    start = time.time()
    while time.time() - start < 5:
        app.processEvents()
        time.sleep(0.1)
    print("[OK] Event loop completed")
    
except Exception as e:
    print(f"[FAIL] UI error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("Done!")
