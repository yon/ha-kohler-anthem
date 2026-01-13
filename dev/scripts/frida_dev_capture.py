#!/usr/bin/env python3
"""Run Kohler app with bypass + traffic capture hooks.

Loads scripts/frida_bypass.js for bypasses, then dev/scripts/frida_capture_hooks.js
for traffic capture. Output is saved to dev/output/capture_<timestamp>.log.
"""

import os
import shutil
import signal
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Paths relative to project root
SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent.parent
BYPASS_SCRIPT = PROJECT_DIR / "scripts" / "frida_bypass.js"
CAPTURE_SCRIPT = SCRIPT_DIR / "frida_capture_hooks.js"
OUTPUT_DIR = PROJECT_DIR / "dev" / "output"

APP_PACKAGE = "com.kohler.hermoth"

# Find frida executable
FRIDA_PATHS = [
    Path.home() / "Library/Python/3.9/bin/frida",
    Path.home() / "Library/Python/3.11/bin/frida",
    Path.home() / "Library/Python/3.12/bin/frida",
]


def find_frida():
    """Find frida executable."""
    # Check PATH first
    frida = shutil.which("frida")
    if frida:
        return frida
    # Check common locations
    for path in FRIDA_PATHS:
        if path.exists():
            return str(path)
    return None


def main():
    # Ensure output dir exists
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Generate output filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = OUTPUT_DIR / f"capture_{timestamp}.log"

    # Check scripts exist
    if not BYPASS_SCRIPT.exists():
        print(f"ERROR: Bypass script not found: {BYPASS_SCRIPT}")
        sys.exit(1)
    if not CAPTURE_SCRIPT.exists():
        print(f"ERROR: Capture script not found: {CAPTURE_SCRIPT}")
        sys.exit(1)

    print("=" * 70)
    print("Kohler Konnect - Dev Traffic Capture")
    print("=" * 70)
    print()
    print(f"Bypass script:  {BYPASS_SCRIPT}")
    print(f"Capture script: {CAPTURE_SCRIPT}")
    print(f"Output file:    {output_file}")
    print()
    # Find frida
    frida_cmd = find_frida()
    if not frida_cmd:
        print("ERROR: frida not found. Install with: pip3 install frida-tools")
        sys.exit(1)

    print("Starting app with Frida...")
    print("Press Ctrl+C to stop capture")
    print()

    # Build frida command - load both scripts
    # Note: newer frida (17.x) doesn't have --no-pause, it resumes by default
    cmd = [
        frida_cmd,
        "-U",  # USB device
        "-f", APP_PACKAGE,  # Spawn app
        "-l", str(BYPASS_SCRIPT),
        "-l", str(CAPTURE_SCRIPT),
    ]

    # Run frida and tee output to file
    try:
        with open(output_file, "w") as f:
            # Write header
            f.write(f"# Kohler Konnect Traffic Capture\n")
            f.write(f"# Started: {datetime.now().isoformat()}\n")
            f.write(f"# Bypass: {BYPASS_SCRIPT}\n")
            f.write(f"# Capture: {CAPTURE_SCRIPT}\n")
            f.write("#" + "=" * 69 + "\n\n")
            f.flush()

            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )

            # Stream output to both console and file
            for line in proc.stdout:
                print(line, end="")
                f.write(line)
                f.flush()

            proc.wait()

    except KeyboardInterrupt:
        print("\n\nCapture stopped by user")
        proc.terminate()

    print()
    print("=" * 70)
    print(f"Capture saved to: {output_file}")
    print("=" * 70)


if __name__ == "__main__":
    main()
