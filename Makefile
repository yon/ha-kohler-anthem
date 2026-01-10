# Kohler Anthem HACS Integration - Setup Makefile
#
# Usage:
#   make install    - Install all required tools
#   make extract    - Extract secrets from APK
#   make proxy      - Start mitmproxy for traffic capture
#   make env        - Generate .env file from captured secrets
#   make test       - Test the configuration
#   make clean      - Remove generated files

SHELL := /bin/bash
.PHONY: install extract proxy env test clean help frida-start frida-stop frida-status bypass

# Directories
SCRIPTS_DIR := scripts
BUILD_DIR := .build
APK_DIR := $(BUILD_DIR)/apk

# Files
ENV_FILE := .env
SECRETS_FILE := $(BUILD_DIR)/secrets.json

help:
	@echo "Kohler Anthem HACS Integration Setup"
	@echo ""
	@echo "Usage:"
	@echo "  make install        Install required tools (Homebrew, Python, Frida, jadx)"
	@echo "  make extract        Extract client_id and api_resource from APK"
	@echo "  make proxy          Start mitmproxy to capture APIM key (requires Frida)"
	@echo "  make env            Generate .env file (interactive)"
	@echo "  make test           Test authentication and device discovery"
	@echo "  make clean          Remove generated files"
	@echo ""
	@echo "Frida (for emulator):"
	@echo "  make frida-start    Start frida-server on emulator (requires adb root)"
	@echo "  make frida-stop     Stop frida-server on emulator"
	@echo "  make frida-status   Check frida connection status"
	@echo "  make bypass         Launch Kohler app with root/SSL bypass"
	@echo ""
	@echo "The APIM key must be captured via mitmproxy + Frida (APK key is outdated)."
	@echo "See SETUP.md for detailed step-by-step instructions."

# =============================================================================
# Step 1: Install Tools
# =============================================================================

install: install-brew install-python install-android install-apk-tools install-frida
	@echo ""
	@echo "=========================================="
	@echo "All tools installed successfully!"
	@echo "=========================================="
	@echo ""
	@echo "Next step: make extract"

install-brew:
	@echo "Checking Homebrew..."
	@which brew > /dev/null || (echo "Installing Homebrew..." && /bin/bash -c "$$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)")
	@echo "Homebrew OK"

install-python:
	@echo "Installing Python dependencies..."
	@brew list python@3.11 > /dev/null 2>&1 || brew install python@3.11
	@pip3 install --quiet mitmproxy frida-tools aiohttp msal
	@echo "Python OK"

install-android:
	@echo "Installing Android tools..."
	@brew list --cask android-platform-tools > /dev/null 2>&1 || brew install --cask android-platform-tools
	@echo "Android Platform Tools OK"
	@echo ""
	@echo "NOTE: You also need an Android emulator or device."
	@echo "      Recommended: Genymotion (https://www.genymotion.com/)"
	@echo "      Or use a physical Android device with USB debugging enabled."

install-frida:
	@echo "Installing Frida..."
	@pip3 install --quiet --upgrade frida-tools
	@echo "Frida OK"

install-apk-tools:
	@echo "Installing APK analysis tools..."
	@brew list jadx > /dev/null 2>&1 || brew install jadx
	@brew list jq > /dev/null 2>&1 || brew install jq
	@echo "APK tools OK"

# =============================================================================
# Step 2: Extract Secrets from APK
# =============================================================================

extract: $(BUILD_DIR) $(SECRETS_FILE)
	@echo ""
	@echo "=========================================="
	@echo "Secrets extracted!"
	@echo "=========================================="
	@cat $(SECRETS_FILE) | jq .
	@echo ""
	@echo "Next step: make proxy"

$(BUILD_DIR):
	@mkdir -p $(BUILD_DIR) $(APK_DIR)

$(SECRETS_FILE): $(BUILD_DIR)
	@echo ""
	@echo "=========================================="
	@echo "APK Extraction"
	@echo "=========================================="
	@echo ""
	@if [ ! -f "$(APK_DIR)/base.apk" ]; then \
		echo "ERROR: APK not found at $(APK_DIR)/base.apk"; \
		echo ""; \
		echo "You need to get the Kohler Konnect APK. Options:"; \
		echo ""; \
		echo "Option A - From your Android device:"; \
		echo "  1. Install 'Kohler Konnect' from Play Store on your device"; \
		echo "  2. Connect device via USB with debugging enabled"; \
		echo "  3. Run: adb shell pm path com.kohler.hermoth"; \
		echo "  4. Run: adb pull <path-from-above> $(APK_DIR)/base.apk"; \
		echo ""; \
		echo "Option B - From APK mirror site:"; \
		echo "  1. Download from apkpure.com or apkmirror.com"; \
		echo "  2. Search for 'Kohler Konnect'"; \
		echo "  3. Save as $(APK_DIR)/base.apk"; \
		echo ""; \
		exit 1; \
	fi
	@echo "Decompiling APK with jadx..."
	@jadx --quiet -d $(APK_DIR)/decompiled $(APK_DIR)/base.apk 2>/dev/null || true
	@echo "Searching for secrets..."
	@python3 $(SCRIPTS_DIR)/extract_secrets_from_apk.py $(APK_DIR)/decompiled > $(SECRETS_FILE)
	@echo "Done!"

# =============================================================================
# Step 3: Capture APIM Key via mitmproxy
# =============================================================================

proxy:
	@echo ""
	@echo "=========================================="
	@echo "Starting mitmproxy"
	@echo "=========================================="
	@echo ""
	@echo "This will capture the APIM subscription key from the Kohler app."
	@echo ""
	@echo "BEFORE YOU CONTINUE, you must:"
	@echo ""
	@echo "1. Have an Android emulator running (Genymotion recommended)"
	@echo "   OR a physical Android device on the same WiFi network"
	@echo ""
	@echo "2. Configure the Android device to use this Mac as a proxy:"
	@echo "   - Go to: Settings > WiFi > (tap your network) > Advanced > Proxy"
	@echo "   - Set Proxy to: Manual"
	@echo "   - Proxy hostname: $$(ipconfig getifaddr en0 || echo YOUR_MAC_IP)"
	@echo "   - Proxy port: 8080"
	@echo "   - Save"
	@echo ""
	@echo "3. Install mitmproxy CA certificate on Android:"
	@echo "   - Open Chrome on Android"
	@echo "   - Go to: http://mitm.it"
	@echo "   - Tap 'Android' to download certificate"
	@echo "   - Go to: Settings > Security > Install from storage"
	@echo "   - Select the downloaded certificate"
	@echo ""
	@echo "4. Install Kohler Konnect app on Android"
	@echo ""
	@echo "Press ENTER when ready, or Ctrl+C to cancel..."
	@read
	@echo ""
	@echo "Starting mitmproxy on port 8080..."
	@echo "A web interface will open at http://localhost:8081"
	@echo ""
	@echo "NOW DO THIS ON ANDROID:"
	@echo "  1. Open Kohler Konnect app"
	@echo "  2. Log in with your Kohler account"
	@echo "  3. Navigate around (view devices, etc.)"
	@echo ""
	@echo "Watch for requests to 'api-kohler-us.kohler.io'"
	@echo "Look for the header: Ocp-Apim-Subscription-Key"
	@echo ""
	@echo "Press Ctrl+C when done capturing."
	@echo ""
	@mitmweb --listen-port 8080 --web-port 8081 -s $(SCRIPTS_DIR)/capture_apim_key.py

# =============================================================================
# Step 4: Generate .env File
# =============================================================================

env:
	@echo ""
	@echo "=========================================="
	@echo "Generate .env Configuration"
	@echo "=========================================="
	@python3 $(SCRIPTS_DIR)/generate_env.py

# =============================================================================
# Step 5: Test Configuration
# =============================================================================

test:
	@echo ""
	@echo "=========================================="
	@echo "Testing Configuration"
	@echo "=========================================="
	@if [ ! -f "$(ENV_FILE)" ]; then \
		echo "ERROR: .env file not found. Run 'make env' first."; \
		exit 1; \
	fi
	@echo "Loading .env and running test..."
	@bash -c 'source $(ENV_FILE) && python3 $(SCRIPTS_DIR)/test_quick_dirty.py'

# =============================================================================
# Cleanup
# =============================================================================

clean:
	@echo "Cleaning up..."
	@rm -rf $(BUILD_DIR)
	@rm -f $(ENV_FILE)
	@echo "Done. Note: .env was removed. Run 'make env' to recreate."

# =============================================================================
# Frida Management (for Genymotion emulator)
# =============================================================================

frida-start:
	@echo "Starting frida-server on emulator..."
	@adb root >/dev/null 2>&1 || true
	@sleep 1
	@adb shell "pkill -9 frida-server 2>/dev/null; /data/local/tmp/frida-server &" &
	@sleep 2
	@echo "Checking frida connection..."
	@frida-ps -U >/dev/null 2>&1 && echo "Frida server running!" || echo "ERROR: Could not connect to frida-server"

frida-stop:
	@echo "Stopping frida-server..."
	@adb shell pkill -9 frida-server 2>/dev/null || true
	@echo "Done"

frida-status:
	@echo "Checking frida connection..."
	@frida-ps -U 2>&1 | head -5 || echo "ERROR: Frida not connected"

bypass:
	@echo "Launching Kohler app with bypass script..."
	@echo "After the app launches, proceed through the location screen and log in."
	@echo ""
	@frida -U -f com.kohler.hermoth -l scripts/frida_ssl_bypass.js
