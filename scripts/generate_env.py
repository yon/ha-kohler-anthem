#!/usr/bin/env python3
"""Interactive script to generate .env file for Kohler Anthem integration.

Collects all required secrets and generates a properly formatted .env file.
"""

import json
import os
import sys
from pathlib import Path

# Paths
SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
BUILD_DIR = PROJECT_DIR / ".build"
ENV_FILE = PROJECT_DIR / ".env"
SECRETS_FILE = BUILD_DIR / "secrets.json"
CAPTURED_FILE = BUILD_DIR / "captured_apim_key.json"


def load_extracted_secrets() -> dict:
    """Load secrets extracted from APK."""
    if SECRETS_FILE.exists():
        try:
            return json.loads(SECRETS_FILE.read_text())
        except Exception:
            pass
    return {}


def load_captured_secrets() -> dict:
    """Load secrets captured from mitmproxy."""
    if CAPTURED_FILE.exists():
        try:
            return json.loads(CAPTURED_FILE.read_text())
        except Exception:
            pass
    return {}


def prompt(message: str, default: str = None, required: bool = True, secret: bool = False) -> str:
    """Prompt user for input with optional default."""
    if default:
        display = f"{message} [{default}]: "
    else:
        display = f"{message}: "

    while True:
        if secret:
            import getpass
            value = getpass.getpass(display)
        else:
            value = input(display).strip()

        if not value and default:
            return default
        if value:
            return value
        if not required:
            return ""
        print("  This field is required. Please enter a value.")


def main():
    print()
    print("=" * 60)
    print("Kohler Anthem .env Generator")
    print("=" * 60)
    print()
    print("This will create a .env file with all the secrets needed")
    print("for the Kohler Anthem Home Assistant integration.")
    print()

    # Load any previously extracted/captured secrets
    extracted = load_extracted_secrets()
    captured = load_captured_secrets()

    secrets = {}

    # =========================================================================
    # APK Secrets (extracted)
    # =========================================================================
    print("-" * 60)
    print("STEP 1: APK Secrets")
    print("-" * 60)
    print()

    if extracted.get("client_id"):
        print(f"  Found CLIENT_ID from APK extraction: {extracted['client_id'][:8]}...")
        secrets["client_id"] = extracted["client_id"]
    else:
        print("  CLIENT_ID not found automatically.")
        print("  You need to extract this from the Kohler Konnect APK.")
        print("  Run 'make extract' first, or enter manually:")
        print()
        secrets["client_id"] = prompt("  KOHLER_CLIENT_ID")

    print()

    if extracted.get("api_resource"):
        print(f"  Found API_RESOURCE from APK extraction: {extracted['api_resource'][:8]}...")
        secrets["api_resource"] = extracted["api_resource"]
    else:
        print("  API_RESOURCE not found automatically.")
        print("  This is usually in the OAuth scope URL in the APK.")
        print()
        secrets["api_resource"] = prompt("  KOHLER_API_RESOURCE")

    print()

    # =========================================================================
    # APIM Key (extracted from APK)
    # =========================================================================
    print("-" * 60)
    print("STEP 2: APIM Subscription Key")
    print("-" * 60)
    print()

    if extracted.get("apim_key"):
        print(f"  Found APIM_KEY from APK extraction: {extracted['apim_key'][:8]}...")
        secrets["apim_key"] = extracted["apim_key"]
    elif captured.get("apim_key"):
        print(f"  Found APIM_KEY from mitmproxy capture: {captured['apim_key'][:8]}...")
        secrets["apim_key"] = captured["apim_key"]
    else:
        print("  APIM_KEY not found.")
        print("  Run 'make extract' to extract it from APK, or enter manually:")
        print()
        secrets["apim_key"] = prompt("  KOHLER_APIM_KEY")

    print()

    # =========================================================================
    # User Credentials
    # =========================================================================
    print("-" * 60)
    print("STEP 3: Your Kohler Account Credentials")
    print("-" * 60)
    print()
    print("  Enter your Kohler Konnect account email and password.")
    print("  These are stored locally in .env (which is gitignored).")
    print()

    secrets["username"] = prompt("  KOHLER_USERNAME (email)")
    secrets["password"] = prompt("  KOHLER_PASSWORD", secret=True)

    print()

    # =========================================================================
    # Device Info (optional - can be discovered)
    # =========================================================================
    print("-" * 60)
    print("STEP 4: Device Info (optional)")
    print("-" * 60)
    print()
    print("  These values are obtained from the device discovery API.")
    print("  If you don't know them, leave blank and run 'make test'")
    print("  to discover them automatically.")
    print()

    secrets["device_id"] = prompt("  KOHLER_DEVICE_ID (e.g., gcs-xxxxxxxxx)", required=False)
    secrets["tenant_id"] = prompt("  KOHLER_TENANT_ID (from JWT, usually same as customer ID)", required=False)

    print()

    # =========================================================================
    # Generate .env file
    # =========================================================================
    print("-" * 60)
    print("Generating .env file...")
    print("-" * 60)
    print()

    env_content = f"""# Kohler Anthem API Configuration
# Generated by generate_env.py
#
# KEEP THIS FILE SECRET - it contains your credentials!
# This file is gitignored and should never be committed.

# Azure AD B2C Authentication (extracted from APK)
export KOHLER_CLIENT_ID="{secrets['client_id']}"
export KOHLER_API_RESOURCE="{secrets['api_resource']}"

# User credentials
export KOHLER_USERNAME="{secrets['username']}"
export KOHLER_PASSWORD="{secrets['password']}"

# Azure APIM Subscription Key (captured via mitmproxy)
export KOHLER_APIM_KEY="{secrets['apim_key']}"

# Device Info (discovered via API)
export KOHLER_DEVICE_ID="{secrets.get('device_id', '')}"
export KOHLER_TENANT_ID="{secrets.get('tenant_id', '')}"

# Azure IoT Hub (optional - for MQTT status updates)
export KOHLER_IOT_HUB_HOST="prd-hub.azure-devices.net"
"""

    ENV_FILE.write_text(env_content)
    os.chmod(ENV_FILE, 0o600)  # Restrict permissions

    print(f"  Created: {ENV_FILE}")
    print(f"  Permissions set to 600 (owner read/write only)")
    print()
    print("=" * 60)
    print("SUCCESS!")
    print("=" * 60)
    print()
    print("Next steps:")
    print()
    print("  1. Run 'make test' to verify your configuration")
    print("  2. The test will discover your DEVICE_ID and TENANT_ID")
    print("  3. Update .env with those values if needed")
    print("  4. Install the HACS integration in Home Assistant")
    print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nCancelled.")
        sys.exit(1)
