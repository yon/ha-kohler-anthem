# Kohler Anthem Digital Shower - Home Assistant Integration

Home Assistant custom integration for the Kohler Anthem Digital Shower system.

## Disclaimer

This integration uses the unofficial [kohler-anthem](https://pypi.org/project/kohler-anthem/) Python library, which was reverse-engineered from the Kohler Konnect mobile app. It is not affiliated with, endorsed by, or supported by Kohler Co. Use at your own risk.

## Features

- **Presets**: Start/stop shower presets (1-5) via switches
- **Warmup**: Preheat water before starting
- **Outlet Control**: Individual control of showerheads, handhelds, body sprays, and steam
- **Temperature**: Set temperature for each outlet (number entities)
- **Spray Patterns**: Select spray intensity patterns (select entities)
- **Status**: Real-time device state via sensors and binary sensors

## Installation (HACS)

1. Add this repository as a custom repository in HACS
2. Search for "Kohler Anthem"
3. Install and restart Home Assistant
4. Add integration via Settings → Devices & Services

## Configuration

The integration requires three credentials extracted from the Kohler Konnect app: `client_id`, `apim_subscription_key`, and `api_resource`. See the [Credential Extraction Guide](https://github.com/yon/kohler-anthem/blob/main/credential-extraction/README.md) for detailed instructions.

### Setup walkthrough

1. **Settings → Devices & Services → Add Integration → Kohler Anthem**.
2. Paste the three extracted credentials and click **Submit**.
3. The integration shows a **clickable authorize URL**. Open it in any browser and sign in with your Kohler account.
4. After signing in, your browser will try to open a custom URL (`msauth.com.kohler.hermoth://auth?code=...`). It will fail — that's expected. **Copy the full URL from your browser's address bar** and paste it back into Home Assistant.
5. Home Assistant exchanges the authorization code for tokens and creates the entry.
6. Subsequent restarts use the persisted refresh token. No re-sign-in until the refresh token expires or is revoked, in which case Home Assistant surfaces a **Repairs** notification.

> **Why this dance?** Kohler's backend started rejecting password-based (ROPC) tokens on shower-control endpoints in May 2026. The `B2C_1A_signin` policy the integration now uses requires an interactive sign-in like the official mobile app does. The custom redirect URI is the same one the official app registers, which keeps things simple — Home Assistant doesn't need to be reachable from your browser.

### Migrating from older versions

If you were running an earlier version that used your Kohler email + password, Home Assistant will surface a Repairs notification on first restart asking you to sign in via the browser. Walk through steps 3–5 above. Your existing entities and automations are preserved (the unique ID stays the same).

## Known Limitations

- **Cloud-dependent**: No local API exists
- **Reverse-engineered**: May break if Kohler changes their API

## License

MIT
