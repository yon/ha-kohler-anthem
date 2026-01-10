# Kohler Anthem HACS Integration - Complete Setup Guide

This guide walks you through extracting all the secrets needed to configure the Kohler Anthem Home Assistant integration. Follow each step exactly as written.

## What You Need

- A Mac with Homebrew
- Your Kohler Konnect account (email + password)
- **Genymotion Android emulator** (required for SSL bypass)
  - Download free: https://www.genymotion.com/download/
  - Physical devices won't work due to SSL pinning

## What You'll Get

By the end of this guide, you'll have a `.env` file with these secrets:

| Secret | What It Is | Where It Comes From |
|--------|-----------|---------------------|
| `KOHLER_CLIENT_ID` | OAuth client ID | Extracted from APK |
| `KOHLER_API_RESOURCE` | OAuth API scope | Extracted from APK |
| `KOHLER_APIM_KEY` | API subscription key | Captured via mitmproxy + Frida |
| `KOHLER_USERNAME` | Your email | You provide |
| `KOHLER_PASSWORD` | Your password | You provide |
| `KOHLER_DEVICE_ID` | Your shower's ID | Discovered via API |
| `KOHLER_TENANT_ID` | Your customer ID | Discovered via API |

**Important:** The APIM key in the APK is outdated and doesn't work. You **MUST** capture the real key using mitmproxy + Frida (Steps 4-5). The APK extraction only gets client_id and api_resource.

---

## Step 0: Clone This Repository

```bash
git clone https://github.com/yon/kohler-anthem-hacs.git
cd kohler-anthem-hacs
```

---

## Step 1: Install Required Tools

Run this command to install all required tools:

```bash
make install
```

This installs:
- Python 3.11 and pip packages (mitmproxy, frida-tools, aiohttp, msal)
- Android Platform Tools (adb)
- jadx (APK decompiler)
- jq (JSON processor)

**Expected output:**
```
Homebrew OK
Python OK
Android Platform Tools OK
Frida OK
APK tools OK

==========================================
All tools installed successfully!
==========================================
```

---

## Step 2: Get the Kohler Konnect APK

You need the Kohler Konnect Android app file (APK). Choose ONE method:

### Method A: From Your Android Phone (Recommended)

1. **Install the app** from Google Play Store:
   - Open Play Store on your phone
   - Search for "Kohler Konnect"
   - Install it

2. **Enable USB debugging** on your phone:
   - Go to: **Settings** → **About phone**
   - Tap "Build number" 7 times (this enables Developer options)
   - Go back to: **Settings** → **Developer options**
   - Enable "USB debugging"

3. **Connect phone to Mac via USB cable**

4. **Accept the debugging prompt** on your phone when it appears

5. **Extract the APK** by running these commands:

   ```bash
   # Create directory for APK
   mkdir -p .build/apk

   # Find where the APK is installed
   adb shell pm path com.kohler.hermoth
   ```

   You'll see output like:
   ```
   package:/data/app/com.kohler.hermoth-XXXX/base.apk
   ```

   Copy that path and run:
   ```bash
   adb pull /data/app/com.kohler.hermoth-XXXX/base.apk .build/apk/base.apk
   ```
   (Replace the path with what you got from the previous command)

### Method B: From APK Mirror Site

1. Go to https://www.apkmirror.com
2. Search for "Kohler Konnect"
3. Download the latest version (choose "APK" not "Bundle")
4. Save the file as `.build/apk/base.apk`

**Verify you have the APK:**
```bash
ls -la .build/apk/base.apk
```

You should see a file around 30-50 MB.

---

## Step 3: Extract Secrets from APK

Run:
```bash
make extract
```

This decompiles the APK and searches for:
- OAuth client ID
- API resource ID
- APIM subscription key (global, same for all users)

**Expected output:**
```
==========================================
APK Extraction
==========================================

Decompiling APK with jadx...
Searching for secrets...
Done!

==========================================
Secrets extracted!
==========================================
{
  "client_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "api_resource": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "apim_key": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
}
```

**Note:** The APK contains an outdated APIM key that doesn't work. You still need to capture the real key using mitmproxy (Steps 4-5).

If client_id or api_resource extraction fails:
1. Try manually searching the `.build/apk/decompiled` folder
2. Look for `msal_config.json` or `auth_config_release.json`

---

## Step 4: Set Up Android for Traffic Capture

> **Required:** The APK contains an outdated APIM key. You must capture the real key via mitmproxy.

You'll capture the APIM key by intercepting traffic from the Kohler app. This requires:
- Mitmproxy running on your Mac
- Android **emulator** (Genymotion) - physical devices won't work
- Frida with our bypass script
- Mitmproxy's CA certificate installed on the emulator

### Why This Is Complicated

The Kohler Konnect app has **aggressive protection** that must be bypassed:

1. **SSL Certificate Pinning** - The app refuses to trust any certificate except Kohler's, which blocks mitmproxy from seeing traffic.

2. **Root Detection** - The app uses RootBeer-based detection with 10+ checks:
   - Checks for `su` binaries in multiple locations
   - Looks for Magisk, SuperSU, Xposed
   - Checks for root management apps
   - Verifies build tags aren't "test-keys"
   - Native library checks

3. **Emulator Detection** - The app detects and refuses to run on emulators:
   - Checks Build.HARDWARE, Build.PRODUCT, Build.MODEL
   - Checks SystemProperties for qemu/goldfish/genymotion
   - Checks TelephonyManager for missing carrier info

**Our Frida script (`scripts/frida_ssl_bypass.js`) bypasses ALL THREE layers:**
- Spoofs Build properties to appear as a Samsung Galaxy S21
- Hooks the obfuscated `Is.b` class to defeat all root checks
- Hooks File.exists/canRead/etc. to hide root paths
- Installs a permissive TrustManager to bypass SSL pinning

**Why Genymotion?** Frida requires root access to inject into apps. Options:
- **Genymotion emulator** (recommended) - Already rooted, easy to push frida-server
- **Physical rooted device** - Works but harder to set up
- **Physical non-rooted device** - Won't work (can't run Frida)

We recommend **Genymotion** (free for personal use): https://www.genymotion.com/download/

### 4a. Install and Set Up Genymotion

1. **Download Genymotion** from https://www.genymotion.com/download/
2. **Install it** (drag to Applications)
3. **Create an account** (free for personal use)
4. **Create a virtual device:**
   - Click "+" to add a new device
   - Choose "Samsung Galaxy S10" or similar (Android 10+)
   - Download and start it

5. **Install Frida server on the emulator:**

   First, install Frida tools if you haven't:
   ```bash
   make install-frida
   ```

   Then download and push frida-server to the emulator:
   ```bash
   # Get the emulator's architecture
   adb shell getprop ro.product.cpu.abi
   # Usually "x86_64" for Genymotion

   # Download frida-server (replace version/arch as needed)
   curl -L -o frida-server.xz https://github.com/frida/frida/releases/download/16.1.4/frida-server-16.1.4-android-x86_64.xz
   xz -d frida-server.xz

   # Push to emulator
   adb push frida-server /data/local/tmp/
   adb shell chmod 755 /data/local/tmp/frida-server
   ```

6. **Install the Kohler Konnect APK:**
   ```bash
   adb install .build/apk/base.apk
   # Or if you have split APKs:
   adb install-multiple apk/*.apk
   ```

### 4b. Find Your Mac's IP Address

Run:
```bash
ipconfig getifaddr en0
```

Note this IP address (e.g., `192.168.1.100`). You'll need it for the proxy settings.

### 4b. Configure Android Proxy

**On your Android phone/emulator:**

1. Go to: **Settings** → **Network & Internet** → **Wi-Fi**
2. Tap and hold on your connected WiFi network
3. Tap **Modify network** (or the gear icon)
4. Tap **Advanced options**
5. Change "Proxy" from "None" to **Manual**
6. Enter:
   - **Proxy hostname:** `[Your Mac's IP from step 4a]`
   - **Proxy port:** `8080`
7. Tap **Save**

### 4c. Install Mitmproxy Certificate on Android

Android apps targeting API 24+ (Android 7+) only trust system certificates, not user-installed ones. For the Kohler app, you need to install the mitmproxy CA as a **system certificate**.

**Step 1: Get the mitmproxy CA certificate**

On your Mac, run mitmproxy once to generate the CA:
```bash
mitmproxy --listen-port 8080
# Press 'q' then 'y' to quit after it starts
```

The CA cert is at: `~/.mitmproxy/mitmproxy-ca-cert.pem`

**Step 2: Convert and push to emulator as system cert**

```bash
# Convert to Android format (hash-named)
CERT_HASH=$(openssl x509 -inform PEM -subject_hash_old -in ~/.mitmproxy/mitmproxy-ca-cert.pem | head -1)
cp ~/.mitmproxy/mitmproxy-ca-cert.pem ${CERT_HASH}.0

# Push to emulator's system certs
adb root
adb remount
adb push ${CERT_HASH}.0 /system/etc/security/cacerts/
adb shell chmod 644 /system/etc/security/cacerts/${CERT_HASH}.0

# Clean up local file
rm ${CERT_HASH}.0
```

**Step 3: Verify installation**

```bash
adb shell ls -la /system/etc/security/cacerts/ | grep -v "2009-01-01"
```

You should see your newly added certificate with today's date.

**Alternative (simpler but less reliable):** Install as user cert via browser:
1. Open Chrome on Android, go to `http://mitm.it` (while mitmproxy runs)
2. Download the Android certificate
3. This may not work for all apps due to network security config

---

## Step 5: Capture the APIM Key

This captures the real API subscription key by bypassing SSL pinning with Frida and intercepting traffic with mitmproxy.

### 5a. Start Frida Server on Emulator

**Important:** Frida-server needs root access on Genymotion. Open a terminal and run:
```bash
# First, get root access
adb root

# Wait a moment, then start frida-server
adb shell /data/local/tmp/frida-server &
```

Verify it's running:
```bash
frida-ps -U | head -5
```

You should see a list of processes. If you see "unable to find process", run `adb root` again.

**Note:** You must restart frida-server after every emulator reboot.

### 5b. Start Mitmproxy

In a **new terminal**, run:
```bash
make proxy
```

This starts mitmproxy on port 8080. Press **ENTER** when prompted.

### 5c. Launch Kohler App with Frida Bypass

In a **third terminal**, launch the app with our Frida bypass script:
```bash
frida -U -f com.kohler.hermoth -l scripts/frida_ssl_bypass.js
```

This:
1. Spawns the Kohler Konnect app
2. Injects our bypass script which:
   - Spoofs device as Samsung Galaxy S21 (defeats emulator detection)
   - Hooks `Is.b` class methods (defeats root detection)
   - Hides root-related file paths (defeats file-based root checks)
   - Installs permissive TrustManager (defeats SSL pinning)
3. Allows the app to run and mitmproxy to see the traffic

**Watch the Frida terminal** - you should see bypass messages like:
```
[*] SSL Pinning + Root Detection + Emulator Detection Bypass loaded
[+] Build properties spoofed to Samsung Galaxy S21
[+] SystemProperties emulator bypass installed
[+] TelephonyManager emulator bypass installed
[+] Kohler Is.b root detection bypass installed
[+] File.* bypass installed
[+] TrustManager bypass installed
[*] All bypasses loaded - try signing in now
```

If the app crashes or shows an error, check the Frida output for which bypass failed.

### 5d. Log In and Capture

**In the emulator:**

1. The Kohler Konnect app should now be open
2. **Log in** with your Kohler account
3. Navigate around:
   - View your devices
   - Tap on your shower

**Watch the mitmproxy terminal.** You should see output like:
```
[Kohler] GET /devices/api/v1/device-management/customer-device/...
         APIM Key: 429e...a493

============================================================
FOUND APIM SUBSCRIPTION KEY!
============================================================

Key: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

Saved to: .build/captured_apim_key.json
============================================================
```

### 5c. Stop Mitmproxy

Once you see "FOUND APIM SUBSCRIPTION KEY!", press **Ctrl+C** to stop mitmproxy.

### 5d. Remove Proxy from Android

**Important!** Remove the proxy settings or your phone won't have internet:

1. Go to: **Settings** → **Network & Internet** → **Wi-Fi**
2. Tap and hold on your WiFi network
3. Tap **Modify network**
4. Tap **Advanced options**
5. Change "Proxy" back to **None**
6. Tap **Save**

---

## Step 6: Generate Your .env File

Run:
```bash
make env
```

This interactive script will:
1. Load secrets extracted from the APK (Step 3)
2. Load the APIM key captured via mitmproxy (Step 5)
3. Ask for your Kohler account credentials
4. Generate a `.env` file

**Follow the prompts:**
```
==========================================
Kohler Anthem .env Generator
==========================================

------------------------------------------------------------
STEP 1: APK Secrets
------------------------------------------------------------

  Found CLIENT_ID from APK extraction: xxxxxxxx...
  Found API_RESOURCE from APK extraction: xxxxxxxx...

------------------------------------------------------------
STEP 2: APIM Subscription Key
------------------------------------------------------------

  Found APIM_KEY from mitmproxy capture: 429e...

------------------------------------------------------------
STEP 3: Your Kohler Account Credentials
------------------------------------------------------------

  KOHLER_USERNAME (email): your_email@example.com
  KOHLER_PASSWORD: [hidden]

------------------------------------------------------------
STEP 4: Device Info (optional)
------------------------------------------------------------

  KOHLER_DEVICE_ID: [press Enter to skip]
  KOHLER_TENANT_ID: [press Enter to skip]

------------------------------------------------------------
Generating .env file...
------------------------------------------------------------

  Created: .env
  Permissions set to 600 (owner read/write only)

==========================================
SUCCESS!
==========================================
```

---

## Step 7: Test Your Configuration

Run:
```bash
make test
```

This will:
1. Authenticate with your credentials
2. Discover your devices
3. Show your DEVICE_ID and TENANT_ID
4. Test sending a command (warmup)

**Expected output:**
```
==========================================
Testing Configuration
==========================================

============================================================
Step 1: Authenticating...
============================================================
   Trying policy: B2C_1_ROPC_Auth
   Status: 200
Authentication successful!

============================================================
Step 2: Discovering devices...
============================================================
✅ Found 1 device(s):
   1. My Shower (ID: gcs-xxxxxxxxx)

============================================================
TEST RESULTS SUMMARY
============================================================
  ✅ Authentication: Success
  ✅ Device Discovery: Found 1 device(s)
     Device ID: gcs-xxxxxxxxx
     Tenant ID: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

### Update .env with Device Info

If the test succeeded, update your `.env` file with the discovered values:

```bash
# Edit .env and fill in KOHLER_DEVICE_ID and KOHLER_TENANT_ID
nano .env
```

---

## Step 8: Install in Home Assistant

1. Copy the `custom_components/kohler_anthem` folder to your Home Assistant's `custom_components` directory

2. Restart Home Assistant

3. Go to: **Settings** → **Devices & Services** → **Add Integration**

4. Search for "Kohler Anthem"

5. Enter your credentials when prompted

---

## Troubleshooting

### "Authentication failed"

- Double-check your email and password
- Make sure you can log into the Kohler Konnect mobile app
- Try resetting your password at kohler.com

### "No devices found"

- Make sure your shower is set up in the Kohler Konnect app
- The device must be provisioned and online

### Mitmproxy shows no Kohler traffic

- Make sure you launched the app with Frida (Step 5c), not by tapping the app icon
- Verify proxy settings on Android (Step 4b)
- Make sure the mitmproxy certificate is installed (Step 4c)
- Check Frida terminal shows all bypasses installed successfully

### Kohler app crashes or shows "rooted device" error

The app detected root/emulator. Check the Frida terminal output:

1. **Missing bypass messages** - The script didn't inject properly. Try:
   ```bash
   frida -U -f com.kohler.hermoth -l scripts/frida_ssl_bypass.js --no-pause
   ```

2. **"Is.b not found"** - Kohler updated their obfuscation. The root detection class name changed. Check `docs/REVERSE_ENGINEERING.md` for how to find the new class name.

3. **App shows "rooted device" error** - A root check wasn't bypassed. Look for `[-]` lines in Frida output showing which hook failed.

4. **All bypasses show installed but still fails** - Make sure you see BOTH:
   - `[+] Kohler Is.b root detection bypass installed`
   - `[+] File.* bypass installed`

   The app uses multiple detection methods. Both Is.b hooks AND File.* hooks are required.

### App shows "Request timeout" after bypasses load

1. **Check location services** - Enable GPS on the emulator:
   ```bash
   adb shell settings put secure location_providers_allowed gps,network
   adb shell settings put secure location_mode 3
   ```

2. **Clear stale proxy settings** - If you previously used mitmproxy:
   ```bash
   adb shell settings delete global http_proxy
   ```

3. **Clear app data and retry** - Cached credentials might be stale:
   ```bash
   adb shell pm clear com.kohler.hermoth
   ```

4. **Restart frida-server** - After emulator reboot/crash:
   ```bash
   adb root
   adb shell pkill frida-server
   adb shell /data/local/tmp/frida-server &
   ```

### Frida shows "unable to find process" or connection errors

```bash
# Restart adb and frida
adb kill-server
adb start-server
adb root
adb shell /data/local/tmp/frida-server &

# Verify connection
frida-ps -U | head -5
```

### Kohler app works but mitmproxy sees nothing

SSL pinning bypass may have failed:
- Check for `[+] TrustManager bypass installed` in Frida output
- Check for `[+] TrustManagerImpl bypass installed` in Frida output
- If missing, the app may be using a different pinning method

### "APIM key not found" after capturing traffic

- Make sure you navigated around in the app (view devices, tap on shower)
- The APIM key is in requests to `api-kohler-us.kohler.io`
- Look for the header `Ocp-Apim-Subscription-Key` in mitmproxy

### APK extraction finds nothing

Try manually searching the decompiled APK:
```bash
grep -r "client_id" .build/apk/decompiled/
grep -r "msal" .build/apk/decompiled/
```

---

## Security Notes

- Your `.env` file contains sensitive credentials
- It's set to mode 600 (only you can read it)
- It's listed in `.gitignore` so it won't be committed
- Never share your `.env` file or its contents

---

## Summary of Commands

```bash
make install   # Install tools
make extract   # Extract secrets from APK
make proxy     # Start mitmproxy to capture APIM key
make env       # Generate .env file
make test      # Test configuration
make clean     # Remove generated files
```
