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

The integration requires credentials extracted from the Kohler Konnect app. See the [Credential Extraction Guide](https://github.com/yon/kohler-anthem/blob/main/credential-extraction/README.md) for detailed instructions on obtaining your `client_id`, `api_resource`, and `apim_key`.

## Known Limitations

- **Cloud-dependent**: No local API exists
- **Reverse-engineered**: May break if Kohler changes their API

## License

MIT
