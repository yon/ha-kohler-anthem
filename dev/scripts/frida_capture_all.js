/*
 * Kohler Konnect - Full Bypass + Traffic Capture
 *
 * This script combines:
 * - Complete SSL/Root/Emulator bypass (required for app to run)
 * - HTTP/OkHttp request capture
 * - IoT Hub connection string capture
 * - MQTT message capture
 * - Command payload capture
 *
 * Usage:
 *   frida -U -f com.kohler.hermoth -l dev/scripts/frida_capture_all.js
 */

if (Java.available) {
    Java.perform(function() {
        console.log("\n" + "=".repeat(70));
        console.log("[*] Kohler Konnect - Full Bypass + Traffic Capture");
        console.log("=".repeat(70) + "\n");

        // =====================================================================
        // SECTION 1: EMULATOR DETECTION BYPASS
        // =====================================================================

        try {
            var Build = Java.use("android.os.Build");
            var origHardware = Build.HARDWARE.value;
            var emulatorIndicators = ["goldfish", "ranchu", "vbox", "genymotion", "sdk", "google_sdk", "generic"];
            var isEmulator = false;

            for (var i = 0; i < emulatorIndicators.length; i++) {
                if (origHardware.toLowerCase().indexOf(emulatorIndicators[i]) !== -1 ||
                    Build.PRODUCT.value.toLowerCase().indexOf(emulatorIndicators[i]) !== -1 ||
                    Build.MODEL.value.toLowerCase().indexOf(emulatorIndicators[i]) !== -1) {
                    isEmulator = true;
                    break;
                }
            }

            if (isEmulator) {
                Build.HARDWARE.value = "exynos2100";
                Build.PRODUCT.value = "o1sxxx";
                Build.MODEL.value = "SM-G991B";
                Build.MANUFACTURER.value = "samsung";
                Build.BRAND.value = "samsung";
                Build.DEVICE.value = "o1s";
                Build.BOARD.value = "exynos2100";
                Build.FINGERPRINT.value = "samsung/o1sxxx/o1s:13/TP1A.220624.014/G991BXXS7DWAA:user/release-keys";
                Build.TAGS.value = "release-keys";
                Build.TYPE.value = "user";
                Build.USER.value = "android-build";
                Build.HOST.value = "build.samsung.com";
                console.log("[+] Build properties spoofed to Samsung Galaxy S21");
            }
        } catch(e) {
            console.log("[-] Build spoof failed: " + e);
        }

        // SystemProperties bypass
        try {
            var SystemProperties = Java.use("android.os.SystemProperties");
            var originalGet = SystemProperties.get.overload('java.lang.String');
            SystemProperties.get.overload('java.lang.String').implementation = function(key) {
                var value = originalGet.call(this, key);
                var spoofProps = {
                    "ro.kernel.qemu": "0",
                    "ro.hardware": "exynos2100",
                    "ro.product.model": "SM-G991B",
                    "ro.product.manufacturer": "samsung",
                    "ro.product.brand": "samsung",
                    "ro.product.device": "o1s",
                    "ro.product.board": "exynos2100",
                    "ro.product.name": "o1sxxx",
                    "ro.build.product": "o1s",
                    "ro.build.fingerprint": "samsung/o1sxxx/o1s:13/TP1A.220624.014/G991BXXS7DWAA:user/release-keys",
                    "ro.build.tags": "release-keys",
                    "ro.build.type": "user",
                    "ro.debuggable": "0",
                    "ro.secure": "1",
                    "init.svc.qemu-props": "",
                    "qemu.sf.lcd_density": "",
                    "ro.kernel.android.qemud": "",
                    "ro.kernel.qemu.gles": "",
                    "ro.boot.hardware": "exynos2100",
                    "gsm.version.baseband": "G991BXXS7DWAA"
                };
                if (spoofProps.hasOwnProperty(key)) {
                    return spoofProps[key];
                }
                if (key.toLowerCase().indexOf("genymotion") !== -1 || key.toLowerCase().indexOf("vbox") !== -1) {
                    return "";
                }
                return value;
            };
            SystemProperties.get.overload('java.lang.String', 'java.lang.String').implementation = function(key, def) {
                var result = SystemProperties.get.overload('java.lang.String').call(this, key);
                return result === "" ? def : result;
            };
            console.log("[+] SystemProperties emulator bypass installed");
        } catch(e) {}

        // TelephonyManager bypass
        try {
            var TelephonyManager = Java.use("android.telephony.TelephonyManager");
            TelephonyManager.getNetworkOperatorName.overload().implementation = function() { return "T-Mobile"; };
            TelephonyManager.getSimOperatorName.overload().implementation = function() { return "T-Mobile"; };
            TelephonyManager.getNetworkOperator.overload().implementation = function() { return "310260"; };
            TelephonyManager.getSimOperator.overload().implementation = function() { return "310260"; };
            TelephonyManager.getPhoneType.overload().implementation = function() { return 1; };
            console.log("[+] TelephonyManager emulator bypass installed");
        } catch(e) {}

        // =====================================================================
        // SECTION 2: ROOT DETECTION BYPASS
        // =====================================================================

        // Kohler's obfuscated root detection class
        try {
            var IsB = Java.use("Is.b");
            IsB.n.implementation = function() { return false; };
            IsB.a.implementation = function() { return false; };
            IsB.b.overload('java.lang.String').implementation = function(s) { return false; };
            IsB.c.implementation = function() { return false; };
            IsB.d.implementation = function() { return false; };
            IsB.e.implementation = function() { return false; };
            IsB.f.implementation = function() { return false; };
            IsB.g.implementation = function() { return false; };
            IsB.h.implementation = function() { return false; };
            IsB.j.implementation = function() { return false; };
            IsB.l.implementation = function() { return false; };
            console.log("[+] Kohler Is.b root detection bypass installed");
        } catch(e) {
            console.log("[-] Is.b not found (class name may have changed): " + e);
        }

        // File-based root detection bypass
        var rootPaths = [
            "/system/xbin/su", "/system/bin/su", "/sbin/su", "/su/bin/su",
            "/data/local/xbin/su", "/data/local/bin/su", "/data/local/su",
            "/system/sd/xbin/su", "/system/bin/failsafe/su",
            "/system/app/Superuser.apk", "/system/app/SuperSU.apk",
            "/system/app/SuperSU/SuperSU.apk",
            "/data/data/com.noshufou.android.su", "/data/data/eu.chainfire.supersu",
            "/data/data/com.koushikdutta.superuser", "/data/data/com.thirdparty.superuser",
            "/data/data/com.topjohnwu.magisk", "/cache/magisk.log",
            "/data/adb/magisk", "/sbin/.magisk",
            "/system/xbin/daemonsu", "/dev/com.koushikdutta.superuser.daemon",
            "/system/bin/.ext/su", "/system/usr/we-need-root/su",
            "/cache/su", "/data/su", "/dev/su",
            "/system/xbin/busybox", "/system/bin/busybox",
            "/product/bin/su", "/odm/bin/su", "/vendor/bin/su", "/vendor/xbin/su"
        ];

        function isRootPath(path) {
            for (var i = 0; i < rootPaths.length; i++) {
                if (path === rootPaths[i]) return true;
            }
            var pathLower = path.toLowerCase();
            var rootPatterns = ["/magisk/", "/.magisk", "/supersu/", "/superuser/", "/xposed/", "/busybox"];
            for (var i = 0; i < rootPatterns.length; i++) {
                if (pathLower.indexOf(rootPatterns[i]) !== -1) return true;
            }
            return false;
        }

        try {
            var File = Java.use("java.io.File");
            File.exists.implementation = function() {
                var path = this.getAbsolutePath();
                if (isRootPath(path)) { return false; }
                return this.exists.call(this);
            };
            File.canRead.implementation = function() {
                var path = this.getAbsolutePath();
                if (isRootPath(path)) { return false; }
                return this.canRead.call(this);
            };
            File.canWrite.implementation = function() {
                var path = this.getAbsolutePath();
                if (isRootPath(path)) { return false; }
                return this.canWrite.call(this);
            };
            File.canExecute.implementation = function() {
                var path = this.getAbsolutePath();
                if (isRootPath(path)) { return false; }
                return this.canExecute.call(this);
            };
            File.isFile.implementation = function() {
                var path = this.getAbsolutePath();
                if (isRootPath(path)) { return false; }
                return this.isFile.call(this);
            };
            File.isDirectory.implementation = function() {
                var path = this.getAbsolutePath();
                if (isRootPath(path)) { return false; }
                return this.isDirectory.call(this);
            };
            console.log("[+] File.* root detection bypass installed");
        } catch(e) {}

        // =====================================================================
        // SECTION 3: SSL PINNING BYPASS
        // =====================================================================

        try {
            var X509TrustManager = Java.use('javax.net.ssl.X509TrustManager');
            var SSLContext = Java.use('javax.net.ssl.SSLContext');
            var TrustManager = Java.registerClass({
                name: 'com.frida.BypassTrustManager',
                implements: [X509TrustManager],
                methods: {
                    checkClientTrusted: function(chain, authType) {},
                    checkServerTrusted: function(chain, authType) {},
                    getAcceptedIssuers: function() { return []; }
                }
            });
            var TrustManagers = [TrustManager.$new()];
            SSLContext.init.overload('[Ljavax.net.ssl.KeyManager;', '[Ljavax.net.ssl.TrustManager;', 'java.security.SecureRandom').implementation = function(km, tm, sr) {
                this.init(km, TrustManagers, sr);
            };
            console.log("[+] TrustManager SSL bypass installed");
        } catch(e) {}

        try {
            var TrustManagerImpl = Java.use('com.android.org.conscrypt.TrustManagerImpl');
            TrustManagerImpl.verifyChain.implementation = function(untrustedChain, trustAnchorChain, host, clientAuth, ocspData, tlsSctData) {
                return untrustedChain;
            };
            console.log("[+] TrustManagerImpl SSL bypass installed");
        } catch(e) {}

        console.log("\n[*] All bypasses installed\n");

        // =====================================================================
        // SECTION 4: HTTP/REST API CAPTURE
        // =====================================================================

        console.log("[*] Installing traffic capture hooks...\n");

        // OkHttp RealCall capture (captures all HTTP requests)
        try {
            var RealCall = Java.use("okhttp3.RealCall");

            RealCall.execute.implementation = function() {
                var request = this.request();
                var url = request.url().toString();
                var method = request.method();

                console.log("\n" + "=".repeat(70));
                console.log("[HTTP " + method + "] " + url);

                // Log headers
                var headers = request.headers();
                for (var i = 0; i < headers.size(); i++) {
                    var name = headers.name(i);
                    var value = headers.value(i);
                    if (name.toLowerCase() === "ocp-apim-subscription-key") {
                        console.log("  " + name + ": " + value);
                    } else if (name.toLowerCase().indexOf("auth") !== -1) {
                        console.log("  " + name + ": " + value.substring(0, 50) + "...");
                    }
                }

                // Log body for non-GET requests
                if (method !== "GET") {
                    var body = request.body();
                    if (body != null) {
                        try {
                            var Buffer = Java.use("okio.Buffer");
                            var buffer = Buffer.$new();
                            body.writeTo(buffer);
                            var bodyStr = buffer.readUtf8();
                            console.log("  Body: " + bodyStr);
                        } catch(e) {}
                    }
                }
                console.log("=".repeat(70));

                return this.execute();
            };

            RealCall.enqueue.implementation = function(callback) {
                var request = this.request();
                var url = request.url().toString();
                var method = request.method();

                console.log("\n" + "=".repeat(70));
                console.log("[HTTP ASYNC " + method + "] " + url);

                if (method !== "GET") {
                    var body = request.body();
                    if (body != null) {
                        try {
                            var Buffer = Java.use("okio.Buffer");
                            var buffer = Buffer.$new();
                            body.writeTo(buffer);
                            var bodyStr = buffer.readUtf8();
                            console.log("  Body: " + bodyStr);
                        } catch(e) {}
                    }
                }
                console.log("=".repeat(70));

                return this.enqueue(callback);
            };
            console.log("[+] OkHttp RealCall capture installed");
        } catch(e) {
            console.log("[-] OkHttp capture failed: " + e);
        }

        // =====================================================================
        // SECTION 5: IOT HUB / MQTT CAPTURE
        // =====================================================================

        // IoT Hub Connection String capture
        try {
            var IotHubConnectionString = Java.use("com.microsoft.azure.sdk.iot.device.IotHubConnectionString");
            IotHubConnectionString.$init.overload('java.lang.String').implementation = function(connectionString) {
                console.log("\n" + "*".repeat(70));
                console.log("[IOT HUB] CONNECTION STRING CAPTURED!");
                console.log("*".repeat(70));
                console.log(connectionString);
                console.log("*".repeat(70) + "\n");
                return this.$init(connectionString);
            };
            console.log("[+] IotHubConnectionString capture installed");
        } catch(e) {}

        // DeviceClient capture
        try {
            var DeviceClient = Java.use("com.microsoft.azure.sdk.iot.device.DeviceClient");
            DeviceClient.$init.overload('java.lang.String', 'com.microsoft.azure.sdk.iot.device.IotHubClientProtocol').implementation = function(connString, protocol) {
                console.log("\n[IOT HUB] DeviceClient created");
                console.log("  Protocol: " + protocol);
                console.log("  Connection: " + connString.substring(0, 50) + "...");
                return this.$init(connString, protocol);
            };
            console.log("[+] DeviceClient capture installed");
        } catch(e) {}

        // IoT Hub Message capture
        try {
            var Message = Java.use("com.microsoft.azure.sdk.iot.device.Message");
            Message.$init.overload('[B').implementation = function(bytes) {
                var str = Java.use("java.lang.String").$new(bytes);
                console.log("\n[IOT MESSAGE] " + str);
                return this.$init(bytes);
            };
            Message.$init.overload('java.lang.String').implementation = function(body) {
                console.log("\n[IOT MESSAGE] " + body);
                return this.$init(body);
            };
            console.log("[+] IoT Hub Message capture installed");
        } catch(e) {}

        // Paho MQTT Client capture
        try {
            var MqttAsyncClient = Java.use("org.eclipse.paho.client.mqttv3.MqttAsyncClient");

            MqttAsyncClient.connect.overload('org.eclipse.paho.client.mqttv3.MqttConnectOptions').implementation = function(options) {
                console.log("\n" + "*".repeat(70));
                console.log("[MQTT] Connecting to: " + this.getServerURI());
                console.log("[MQTT] Client ID: " + this.getClientId());
                if (options) {
                    try {
                        console.log("[MQTT] Username: " + options.getUserName());
                    } catch(e) {}
                }
                console.log("*".repeat(70) + "\n");
                return this.connect(options);
            };

            MqttAsyncClient.publish.overload('java.lang.String', 'org.eclipse.paho.client.mqttv3.MqttMessage').implementation = function(topic, message) {
                console.log("\n[MQTT PUBLISH] Topic: " + topic);
                try {
                    var payload = message.getPayload();
                    var payloadStr = Java.use("java.lang.String").$new(payload);
                    console.log("[MQTT PUBLISH] Payload: " + payloadStr);
                } catch(e) {}
                return this.publish(topic, message);
            };
            console.log("[+] Paho MQTT capture installed");
        } catch(e) {}

        // =====================================================================
        // SECTION 6: COMMAND/JSON CAPTURE
        // =====================================================================

        // Gson serialization capture (captures command objects)
        try {
            var Gson = Java.use("com.google.gson.Gson");
            Gson.toJson.overload('java.lang.Object').implementation = function(obj) {
                var json = this.toJson(obj);
                var className = obj.getClass().getName();

                // Filter for interesting classes
                var isInteresting =
                    className.indexOf("kohler") !== -1 ||
                    className.indexOf("hermoth") !== -1 ||
                    className.indexOf("Command") !== -1 ||
                    className.indexOf("Request") !== -1 ||
                    className.indexOf("Preset") !== -1 ||
                    className.indexOf("Warmup") !== -1 ||
                    className.indexOf("Valve") !== -1 ||
                    className.indexOf("Outlet") !== -1 ||
                    json.indexOf("deviceId") !== -1 ||
                    json.indexOf("presetId") !== -1 ||
                    json.indexOf("experienceId") !== -1 ||
                    json.indexOf("temperatureSetpoint") !== -1 ||
                    json.indexOf("flowSetpoint") !== -1;

                if (isInteresting && className.indexOf("microsoft") === -1) {
                    console.log("\n[GSON] " + className);
                    console.log(json);
                }
                return json;
            };
            console.log("[+] Gson command capture installed");
        } catch(e) {}

        // Retrofit request body capture
        try {
            var GsonRequestBodyConverter = Java.use("retrofit2.converter.gson.GsonRequestBodyConverter");
            GsonRequestBodyConverter.convert.overload('java.lang.Object').implementation = function(value) {
                var className = value.getClass().getName();
                console.log("\n[RETROFIT] " + className);
                try {
                    var Gson = Java.use("com.google.gson.Gson");
                    var gson = Gson.$new();
                    console.log(gson.toJson(value));
                } catch(e) {}
                return this.convert(value);
            };
            console.log("[+] Retrofit request body capture installed");
        } catch(e) {}

        // =====================================================================
        // READY
        // =====================================================================

        console.log("\n" + "=".repeat(70));
        console.log("[*] ALL CAPTURE HOOKS INSTALLED");
        console.log("=".repeat(70));
        console.log("[*] Now sign in and control the shower");
        console.log("[*] Watch for:");
        console.log("    [HTTP]        - REST API requests");
        console.log("    [IOT HUB]     - IoT Hub connection strings");
        console.log("    [IOT MESSAGE] - Messages to IoT Hub");
        console.log("    [MQTT]        - MQTT connections and publishes");
        console.log("    [GSON]        - Command objects being serialized");
        console.log("    [RETROFIT]    - Request bodies");
        console.log("=".repeat(70) + "\n");

    });
}
