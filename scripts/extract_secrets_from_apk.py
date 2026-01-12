#!/usr/bin/env python3
"""Extract authentication secrets from decompiled Kohler Konnect APK.

Usage:
    python3 extract_secrets_from_apk.py /path/to/decompiled/apk

Outputs JSON with CLIENT_ID, API_RESOURCE, and APIM_KEY.
"""

import json
import os
import re
import sys
from pathlib import Path


def find_msal_config(decompiled_path: Path) -> dict:
    """Search for MSAL configuration containing client_id."""
    results = {"client_id": None, "api_resource": None, "apim_key": None}

    # Search patterns
    client_id_pattern = re.compile(r'"client_id"\s*:\s*"([a-f0-9-]{36})"', re.IGNORECASE)
    # API resource is often in scope URLs
    scope_pattern = re.compile(r'https://[^/]+/([a-f0-9-]{36})/', re.IGNORECASE)
    # APIM key is hardcoded in OkHttp interceptor
    apim_pattern = re.compile(r'"Ocp-Apim-Subscription-Key",\s*"([a-f0-9]{32})"')

    # Walk through all files
    for root, dirs, files in os.walk(decompiled_path):
        for filename in files:
            if not filename.endswith(('.java', '.json', '.xml', '.smali')):
                continue

            filepath = Path(root) / filename
            try:
                content = filepath.read_text(encoding='utf-8', errors='ignore')

                # Look for client_id
                if not results["client_id"]:
                    match = client_id_pattern.search(content)
                    if match:
                        results["client_id"] = match.group(1)

                # Look for API resource in scope URLs
                if not results["api_resource"]:
                    match = scope_pattern.search(content)
                    if match:
                        # Verify it's not the client_id
                        resource = match.group(1)
                        if resource != results.get("client_id"):
                            results["api_resource"] = resource

                # Look for APIM subscription key
                if not results["apim_key"]:
                    match = apim_pattern.search(content)
                    if match:
                        results["apim_key"] = match.group(1)

                # Stop if we found all three
                if results["client_id"] and results["api_resource"] and results["apim_key"]:
                    break

            except Exception:
                continue

    return results


def find_in_resources(decompiled_path: Path) -> dict:
    """Search in resources/assets for msal_config.json and other config files."""
    results = {"client_id": None, "api_resource": None, "apim_key": None}

    # Common locations for MSAL config
    possible_paths = [
        decompiled_path / "resources" / "assets" / "msal_config.json",
        decompiled_path / "assets" / "msal_config.json",
        decompiled_path / "res" / "raw" / "msal_config.json",
        decompiled_path / "resources" / "res" / "raw" / "msal_config.json",
        decompiled_path / "resources" / "res" / "raw" / "auth_config_release.json",
    ]

    for config_path in possible_paths:
        if config_path.exists():
            try:
                config = json.loads(config_path.read_text())
                if "client_id" in config:
                    results["client_id"] = config["client_id"]
                # Check for scopes
                if "scopes" in config:
                    for scope in config.get("scopes", []):
                        match = re.search(r'/([a-f0-9-]{36})/', scope)
                        if match and match.group(1) != results.get("client_id"):
                            results["api_resource"] = match.group(1)
                            break
            except Exception:
                continue

    return results


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 extract_secrets_from_apk.py /path/to/decompiled/apk", file=sys.stderr)
        sys.exit(1)

    decompiled_path = Path(sys.argv[1])

    if not decompiled_path.exists():
        print(f"Error: Path does not exist: {decompiled_path}", file=sys.stderr)
        sys.exit(1)

    # Try resources first (faster)
    results = find_in_resources(decompiled_path)

    # Fall back to full search if needed
    if not results["client_id"] or not results["api_resource"] or not results["apim_key"]:
        full_results = find_msal_config(decompiled_path)
        if not results["client_id"]:
            results["client_id"] = full_results["client_id"]
        if not results["api_resource"]:
            results["api_resource"] = full_results["api_resource"]
        if not results["apim_key"]:
            results["apim_key"] = full_results["apim_key"]

    # Validate
    if not results["client_id"]:
        print("Warning: Could not find client_id in APK", file=sys.stderr)
    if not results["api_resource"]:
        print("Warning: Could not find api_resource in APK", file=sys.stderr)
    if not results["apim_key"]:
        print("Warning: Could not find apim_key in APK", file=sys.stderr)

    # Output JSON
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
