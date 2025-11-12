# ProtonVPN Public Port Refresh for macOS

[![Python](https://img.shields.io/badge/python-3.7+-blue.svg)](https://www.python.org/)
[![macOS](https://img.shields.io/badge/platform-macOS-lightgrey.svg)](https://www.apple.com/macos/)
[![Coverage](https://img.shields.io/badge/coverage-68%25-green.svg)](htmlcov/index.html)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Version](https://img.shields.io/badge/version-1.1.0-blue.svg)]()

A Python script for macOS that maintains dynamic public ports for ProtonVPN connections using NAT-PMP. It periodically refreshes the port mapping and can optionally control macOS applications (e.g., torrent clients) by updating their configurations and restarting them when the port changes.

**Note:** This script is designed for ProtonVPN with P2P access enabled and WireGuard protocol. Other VPNs or protocols may not support NAT-PMP port forwarding.

## Author

Kent <kent@bci.com> with assistance from GitHub Copilot and Grok Code Fast 1

## Keywords
macos, protonvpn, nat-pmp, folx

## Features

- **Automatic Port Refreshing**: Periodically refreshes ProtonVPN's public port via NAT-PMP to maintain connectivity.
- **Application Control**: Optionally controls specified macOS applications, updating their port settings and restarting them on port changes.
- **VPN Status Checking**: Checks and displays VPN connection status, including interface detection and NAT-PMP support.
- **Network Diagnostics**: Runs diagnostics to test connectivity, NAT-PMP functionality, and network information.
- **Graceful Shutdown**: Handles SIGINT (Ctrl+C) for clean termination.
- **Logging**: Configurable logging levels for debugging and monitoring.

## Installation

### Prerequisites

- macOS
- Python 3.7+
- NAT-PMP client installed at `~/Library/Python/3.9/bin/natpmp-client.py` (or adjust `NAT_PMP_PATH` in the script)
- Configured ProtonVPN connection with NAT-PMP support

### ProtonVPN Setup

To use this script effectively:

1. **ProtonVPN Account**: Sign up for ProtonVPN (free or paid). P2P access requires a paid plan.
2. **P2P Access**: Enable P2P/file sharing in your ProtonVPN account settings. This allows torrenting and port forwarding.
3. **WireGuard Protocol**: Use WireGuard in the ProtonVPN app for faster speeds and better NAT-PMP support. See [ProtonVPN WireGuard setup for macOS](https://protonvpn.com/support/wireguard-manual-macos/) for detailed instructions.
4. **Server Selection**: Connect to a P2P-enabled server (marked with P2P icon in the app). Not all servers support NAT-PMP.
5. **Test Connection**: Run `protonvpn_public_port_refresh.py --vpn-status` to verify NAT-PMP support.

**Why WireGuard?** WireGuard provides modern, efficient tunneling with reliable NAT-PMP port forwarding, essential for dynamic port management in P2P applications.

### Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/bci/protonvpn_public_port_refresh_macos.git
   cd protonvpn_public_port_refresh_macos
   ```

2. Ensure the NAT-PMP client is installed and accessible.

3. Make the script executable:
   ```bash
   chmod +x protonvpn_public_port_refresh.py
   ```

## Usage

### Basic Usage

Run the script to start refreshing the public port:

```bash
python3 protonvpn_public_port_refresh.py
```

### Command-Line Options

- `--app-control APPS`: Comma-separated list of apps to control (default: none)
- `--app-list`: Display all configured apps and exit
- `--diagnostics`: Run network diagnostics
- `--help`: Show help message
- `--loglevel LEVEL`: Log level: debug, info, warning, error (default: info)
- `--network-info`: Display network information
- `--pmt-timeout PMT_TIMEOUT`: Timeout for NAT-PMP operations in seconds (default: 30)
- `--refresh-seconds SECONDS`: Interval to refresh port (default: 45)
- `--status`: Show real-time status screen with curses interface
- `--status-timeout TIMEOUT`: Timeout for status screen in seconds (default: no timeout)
- `--vpn-gateway GATEWAY`: VPN gateway IP (default: 10.2.0.1)
- `--vpn-status`: Check and display VPN connection status

### Examples

#### Basic Port Refreshing
```bash
python3 protonvpn_public_port_refresh.py
```

#### Control Folx with Custom Refresh Interval
```bash
python3 protonvpn_public_port_refresh.py --app-control Folx3-setapp --refresh-seconds 60
```

#### Check VPN Status
```bash
python3 protonvpn_public_port_refresh.py --vpn-status
```

#### Show Real-time Status Screen
```bash
python3 protonvpn_public_port_refresh.py --status
```

#### Show Status Screen with Timeout
```bash
python3 protonvpn_public_port_refresh.py --status --status-timeout 30
```

#### Verbose Logging
```bash
python3 protonvpn_public_port_refresh.py --loglevel debug --app-control Folx3-setapp
```

## Supported Applications

The script can control macOS applications that support port configuration. Currently supported apps (defined in `APPS_CONFIG`):

### Folx v3 (Setapp) - `Folx3-setapp`

**Description**: Folx is a download manager and torrent client available via Setapp subscription.

**Configuration**:
- **App Bundle Path**: `/Applications/Setapp/Folx.app`
- **macOS Defaults Domain**: `com.eltima.Folx3-setapp`
- **Port Setting**: The script updates the `TorrentTCPPort` setting in `GeneralUserSettings` via `defaults write`
- **Start Command**: Uses `open` to launch the application
- **Stop Command**: Uses AppleScript to quit the app (`quit app "Folx"`)

**Requirements**:
- Folx v3 must be installed via Setapp
- The app must be configured to use the dynamic port for torrent downloads
- Ensure Folx is set to listen on the configured port in its preferences

To add more apps, edit the `APPS_CONFIG` dictionary in the script with the appropriate paths, defaults domains, and control functions.

## Testing

Run the included test suite:

```bash
python3 -m pytest test_protonvpn_refresh.py
```

## Contributing

Contributions are welcome! Please fork the repository and submit a pull request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Disclaimer

This script is provided as-is. Ensure you comply with ProtonVPN's terms of service and local laws regarding port forwarding and application usage.