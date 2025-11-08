#!/usr/bin/env python3
"""
protonvpn-public-port-refresh.py
Refreshes ProtonVPN public port periodically and controls specified applications.

DESCRIPTION:
This script maintains the dynamic public port for ProtonVPN connections by periodically
refreshing the NAT-PMP mapping. It can optionally control macOS applications that depend
on the public port, such as torrent clients, by updating their configuration and restarting
them when the port changes.

The script waits for an initial successful port acquisition before starting any controlled
applications. It continues to refresh the port at the specified interval and handles port
changes by restarting applications if needed. The script can be stopped gracefully at any
time using Ctrl+C.

USAGE:
    python3 protonvpn-public-port-refresh.py [options]

OPTIONS:
    --refresh-seconds SECONDS    Interval to refresh port (default: 45)
    --vpn-gateway GATEWAY        VPN gateway IP (default: 10.2.0.1)
    --app-control APPS           Comma-separated list of apps to control (default: none)
    --loglevel LEVEL             Log level: debug, info, warning, error (default: info)
    --pmt-timeout PMT_TIMEOUT    Timeout for NAT-PMP operations in seconds (default: 30)
    --app-list                   Display all configured apps and exit
    --vpn-status                 Check and display VPN connection status
    --diagnostics                Run network diagnostics
    --network-info               Display network information
    --help                       Show this help

EXAMPLES:
    # Basic port refreshing without app control
    python3 protonvpn-public-port-refresh.py

    # Control Folx with custom refresh interval
    python3 protonvpn-public-port-refresh.py --app-control Folx3-setapp --refresh-seconds 60

    # List available apps
    python3 protonvpn-public-port-refresh.py --app-list

    # Verbose logging
    python3 protonvpn-public-port-refresh.py --loglevel info --app-control Folx3-setapp

    # Debug logging with maximum verbosity
    python3 protonvpn-public-port-refresh.py --loglevel debug --app-control Folx3-setapp

    # Custom PMT timeout for slow connections
    python3 protonvpn-public-port-refresh.py --pmt-timeout 120 --app-control Folx3-setapp

    # Check VPN status
    python3 protonvpn-public-port-refresh.py --vpn-status

    # Run network diagnostics
    python3 protonvpn-public-port-refresh.py --diagnostics

    # Display network information
    python3 protonvpn-public-port-refresh.py --network-info

REQUIREMENTS:
    - natpmp-client.py installed at ~/Library/Python/3.9/bin/
    - Configured applications must be properly installed
    - ProtonVPN connection with NAT-PMP support

NOTES:
    - The script uses SIGINT (Ctrl+C) for graceful shutdown
    - Applications are started after first successful port acquisition
    - Port changes trigger application restart with 30-second wait
    - All static configuration is in the APPS_CONFIG dictionary
"""

import argparse
import logging
import os
import signal
import subprocess
import sys
import time
from datetime import datetime

# GitHub Copilot Terminal Integration
# Using available terminal tools for enhanced functionality

# Configuration
NAT_PMP_PATH = os.path.expanduser("~/Library/Python/3.9/bin/natpmp-client.py")

# APPS_CONFIG: Dictionary of applications that can be controlled.
# Each key is the app name (used in --app-control).
# Each value is a dict with:
#   - "path": Full path to the application bundle
#   - "defaults": macOS defaults domain for storing settings
#   - "start": Function to start the app (takes path as arg)
#   - "stop": Function to stop the app (no args)
def start_folx(path):
    """Start the Folx application."""
    subprocess.run(["open", path], check=True)

def stop_folx():
    """Stop the Folx application."""
    subprocess.run(["osascript", "-e", 'quit app "Folx"'], check=True)

APPS_CONFIG = {
    "Folx3-setapp": {
        "path": "/Applications/Setapp/Folx.app",
        "defaults": "com.eltima.Folx3-setapp",
        "start": start_folx,
        "stop": stop_folx,
    },
    # Add more apps here if needed
}

class PortRefresher:
    """
    Main class for managing ProtonVPN port refreshing and application control.
    
    Handles the refresh loop, port monitoring, and application lifecycle management.
    """
    def __init__(self, refresh_seconds, vpn_gateway, app_control, loglevel, pmt_timeout=30):
        """
        Initialize the PortRefresher.
        
        Args:
            refresh_seconds (int): Seconds between port refresh attempts
            vpn_gateway (str): IP address of VPN gateway
            app_control (str): Comma-separated app names to control
            loglevel (str): Logging level (debug, info, warning, error)
            pmt_timeout (int): Timeout for NAT-PMP operations in seconds
        """
        self.refresh_seconds = refresh_seconds
        self.vpn_gateway = vpn_gateway
        self.app_control = app_control.split(',') if app_control else []
        self.stopped = False
        self.current_port = None
        self.port_changed_count = 0
        self.last_change_time = None
        self.pmt_timeout = pmt_timeout

        # Setup logging
        loglevel_map = {
            'debug': logging.DEBUG,
            'info': logging.INFO,
            'warning': logging.WARNING,
            'error': logging.ERROR,
            'critical': logging.CRITICAL
        }
        if loglevel.lower() not in loglevel_map:
            raise ValueError(f'Invalid log level: {loglevel}. Must be one of: {", ".join(loglevel_map.keys())}')
        numeric_level = loglevel_map[loglevel.lower()]
        logging.basicConfig(level=numeric_level, format='%(asctime)s - %(levelname)s - %(message)s')

        # Signal handler for graceful stop
        signal.signal(signal.SIGINT, self.signal_handler)

    def signal_handler(self, signum, frame):
        """Handle SIGINT signal for graceful shutdown."""
        logging.info("Received signal to stop. Shutting down...")
        self.stopped = True

    def get_public_port(self, timeout=None):
        """
        Retrieve the current public port using NAT-PMP.
        
        Args:
            timeout (int, optional): Timeout in seconds for the command
            
        Returns:
            int or None: The public port number, or None if failed
        """
        try:
            result = subprocess.run([
                NAT_PMP_PATH, "-g", self.vpn_gateway, "0", "0"
            ], capture_output=True, text=True, check=True, timeout=timeout)
            # Parse the output: assuming space-separated, 15th field (0-based index 14), then split by comma
            parts = result.stdout.strip().split()
            if len(parts) > 14:
                port_str = parts[14].split(',')[0]
                return int(port_str)
            else:
                logging.error("Unexpected output format from natpmp-client")
                return None
        except subprocess.TimeoutExpired:
            logging.warning(f"NAT-PMP command timed out after {timeout} seconds")
            return None
        except subprocess.CalledProcessError as e:
            logging.warning(f"Failed to get public port: {e}")
            return None
        except FileNotFoundError:
            logging.error(f"natpmp-client.py not found at {NAT_PMP_PATH}. Please ensure it's installed.")
            sys.exit(1)
        except ValueError:
            logging.error("Failed to parse port number")
            return None

    def control_app(self, app_name, action):
        """
        Perform an action on a controlled application.
        
        Args:
            app_name (str): Name of the application
            action (str): Action to perform ('start', 'stop', 'set_port')
        """
        if app_name not in APPS_CONFIG:
            logging.warning(f"Unknown app: {app_name}")
            return
        config = APPS_CONFIG[app_name]
        try:
            if action == "start":
                logging.info(f"Starting {app_name}")
                config["start"](config["path"])
            elif action == "stop":
                logging.info(f"Stopping {app_name}")
                config["stop"]()
            elif action == "set_port":
                logging.info(f"Setting port {self.current_port} for {app_name}")
                subprocess.run([
                    "defaults", "write", config["defaults"], "GeneralUserSettings", "-dict-add", "TorrentTCPPort", str(self.current_port)
                ], check=True)
        except subprocess.CalledProcessError as e:
            logging.error(f"Failed to {action} {app_name}: {e}")

    def start_apps(self):
        """Start all controlled applications and set their port configuration."""
        for app in self.app_control:
            self.control_app(app, "set_port")
            self.control_app(app, "start")

    def stop_apps(self):
        """Stop all controlled applications."""
        for app in self.app_control:
            self.control_app(app, "stop")

    def check_vpn_connection(self):
        """
        Check VPN connection status using terminal commands.
        
        Returns:
            dict: VPN status information
        """
        status = {
            'connected': False,
            'gateway': self.vpn_gateway,
            'interface': None,
            'natpmp_supported': False
        }
        
        try:
            # Check routing table for VPN gateway via utun interface
            route_result = self.run_diagnostic_command("netstat -nr")
            if route_result['success']:
                lines = route_result['output'].split('\n')
                for line in lines:
                    parts = line.split()
                    if len(parts) >= 6 and parts[0] == self.vpn_gateway and parts[5].startswith('utun'):
                        status['connected'] = True
                        status['interface'] = parts[5]
                        break
            
            # Test NAT-PMP support
            port = self.get_public_port(timeout=self.pmt_timeout)
            if port is not None:
                status['natpmp_supported'] = True
                
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
            logging.debug("Could not check VPN connection status")
            
        return status

    def run_diagnostic_command(self, command):
        """
        Run a diagnostic command in the terminal.
        
        Args:
            command (str): Command to run
            
        Returns:
            dict: Command result with output and success status
        """
        result = {
            'command': command,
            'success': False,
            'output': '',
            'error': ''
        }
        
        try:
            # Use subprocess for safe command execution
            proc = subprocess.run(
                command, 
                shell=True, 
                capture_output=True, 
                text=True, 
                timeout=30
            )
            result['success'] = proc.returncode == 0
            result['output'] = proc.stdout
            result['error'] = proc.stderr
            
        except subprocess.TimeoutExpired:
            result['error'] = "Command timed out after 30 seconds"
        except Exception as e:
            result['error'] = str(e)
            
        return result

    def get_network_info(self):
        """
        Get network information using terminal commands.
        
        Returns:
            dict: Network information
        """
        info = {}
        
        # Get routing table
        route_result = self.run_diagnostic_command("netstat -nr")
        if route_result['success']:
            info['routing_table'] = route_result['output']
        
        # Get network interfaces
        ifconfig_result = self.run_diagnostic_command("ifconfig")
        if ifconfig_result['success']:
            info['interfaces'] = ifconfig_result['output']
            
        # Check DNS resolution
        dns_result = self.run_diagnostic_command("nslookup google.com")
        info['dns_working'] = dns_result['success']
        
        return info

    def run(self):
        """
        Main execution loop.
        
        Acquires initial port, starts apps, then enters refresh loop until stopped.
        """
        logging.info("Starting ProtonVPN public port refresher")
        logging.info(f"Refresh interval: {self.refresh_seconds} seconds")
        logging.info(f"VPN gateway: {self.vpn_gateway}")
        if self.app_control:
            logging.info(f"Controlling apps: {', '.join(self.app_control)}")
        else:
            logging.info("No apps to control")

        # Acquire initial port
        logging.info("Requesting initial public port...")
        start_time = time.time()
        retry_count = 0
        max_retries = 10  # Prevent infinite retries
        
        while not self.stopped and retry_count < max_retries:
            elapsed_time = time.time() - start_time
            if elapsed_time >= 300:  # 5 minute overall timeout for initial acquisition
                logging.error(f"Timeout: Failed to acquire initial public port after {elapsed_time:.1f} seconds ({retry_count} retries)")
                logging.error("Please check your VPN connection and NAT-PMP support")
                return
            
            self.current_port = self.get_public_port(timeout=self.pmt_timeout)
            if self.current_port is not None:
                logging.info(f"Initial public port acquired after {elapsed_time:.1f} seconds")
                break
                
            retry_count += 1
            logging.warning(f"VPN gateway does not support NAT-PMP or connection issue. Retry {retry_count} in 30 seconds...")
            time.sleep(30)
            
        if self.stopped:
            return

        self.port_changed_count = 0
        self.last_change_time = datetime.now()
        logging.info(f"Initial public port acquired: {self.current_port}")
        if self.app_control:
            self.start_apps()

        # Main refresh loop
        while not self.stopped:
            time.sleep(self.refresh_seconds)
            if self.stopped:
                break
            port = self.get_public_port(timeout=self.pmt_timeout)
            if port is None:
                logging.warning("Failed to refresh port. Retrying in 30 seconds...")
                time.sleep(30)
                continue
            if port != self.current_port:
                self.port_changed_count += 1
                self.current_port = port
                self.last_change_time = datetime.now()
                logging.info(f"Public port changed to {port}")
                if self.app_control:
                    logging.info("Restarting controlled apps")
                    self.stop_apps()
                    time.sleep(30)  # Wait for stop
                    self.start_apps()

            logging.info(f"Public port: {self.current_port}, changed {self.port_changed_count} time(s), last at {self.last_change_time}")
            logging.info(f"Next refresh in {self.refresh_seconds} seconds. Press Ctrl+C to stop.")

        logging.info("Stopping refresher")
        if self.app_control:
            self.stop_apps()

def main():
    """
    Main entry point.
    
    Parses command-line arguments and either displays app list or starts the refresher.
    """
    parser = argparse.ArgumentParser(description="Refresh ProtonVPN public port")
    parser.add_argument("--refresh-seconds", type=int, default=45, help="Refresh interval in seconds (default: 45)")
    parser.add_argument("--vpn-gateway", default="10.2.0.1", help="VPN gateway IP (default: 10.2.0.1)")
    parser.add_argument("--app-control", default="", help="Comma-separated list of apps to control (default: none)")
    parser.add_argument("--loglevel", default="info", choices=["debug", "info", "warning", "error"], help="Log level (default: info)")
    parser.add_argument("--pmt-timeout", type=int, default=30, help="Timeout for NAT-PMP operations in seconds (default: 30)")
    parser.add_argument("--app-list", action="store_true", help="Display all configured apps")
    parser.add_argument("--vpn-status", action="store_true", help="Check and display VPN connection status")
    parser.add_argument("--diagnostics", action="store_true", help="Run network diagnostics")
    parser.add_argument("--network-info", action="store_true", help="Display network information")

    args = parser.parse_args()

    # Initialize logging early so debug messages work
    loglevel_map = {
        'debug': logging.DEBUG,
        'info': logging.INFO,
        'warning': logging.WARNING,
        'error': logging.ERROR,
        'critical': logging.CRITICAL
    }
    if args.loglevel.lower() not in loglevel_map:
        raise ValueError(f'Invalid log level: {args.loglevel}. Must be one of: {", ".join(loglevel_map.keys())}')
    numeric_level = loglevel_map[args.loglevel.lower()]
    logging.basicConfig(level=numeric_level, format='%(asctime)s - %(levelname)s - %(message)s')

    logging.debug(f"Parsed arguments: refresh_seconds={args.refresh_seconds}, vpn_gateway={args.vpn_gateway}, app_control='{args.app_control}', loglevel={args.loglevel}, pmt_timeout={args.pmt_timeout}, app_list={args.app_list}, vpn_status={args.vpn_status}, diagnostics={args.diagnostics}, network_info={args.network_info}")

    # Handle terminal integration features
    if args.vpn_status:
        logging.debug("VPN status check requested")
        # Create a temporary refresher just for status checking
        temp_refresher = PortRefresher(args.refresh_seconds, args.vpn_gateway, args.app_control, args.loglevel, args.pmt_timeout)
        status = temp_refresher.check_vpn_connection()
        print("VPN Connection Status:")
        print(f"  Connected: {status['connected']}")
        print(f"  Gateway: {status['gateway']}")
        print(f"  Interface: {status['interface'] or 'Not detected'}")
        print(f"  NAT-PMP Supported: {status['natpmp_supported']}")
        return
        
    if args.diagnostics:
        logging.debug("Network diagnostics requested")
        temp_refresher = PortRefresher(args.refresh_seconds, args.vpn_gateway, args.app_control, args.loglevel, args.pmt_timeout)
        print("Running Network Diagnostics...")
        
        # Test basic connectivity
        ping_result = temp_refresher.run_diagnostic_command("ping -c 3 8.8.8.8")
        print(f"Internet Connectivity: {'✓' if ping_result['success'] else '✗'}")
        if not ping_result['success']:
            print(f"  Error: {ping_result['error']}")
            
        # Test NAT-PMP
        port = temp_refresher.get_public_port(timeout=args.pmt_timeout)
        print(f"NAT-PMP Port Acquisition: {'✓' if port else '✗'}")
        if port:
            print(f"  Current Port: {port}")
            
        return
        
    if args.network_info:
        logging.debug("Network info requested")
        temp_refresher = PortRefresher(args.refresh_seconds, args.vpn_gateway, args.app_control, args.loglevel, args.pmt_timeout)
        info = temp_refresher.get_network_info()
        print("Network Information:")
        print(f"DNS Resolution: {'✓' if info.get('dns_working', False) else '✗'}")
        if 'interfaces' in info:
            print("Network Interfaces:")
            # Show only key interface info
            lines = info['interfaces'].split('\n')
            current_iface = None
            for line in lines[:20]:  # Limit output
                if line and not line.startswith('\t'):
                    current_iface = line.split(':')[0]
                    print(f"  {current_iface}")
                elif line.startswith('\tinet ') and current_iface:
                    ip = line.strip().split()[1]
                    print(f"    IP: {ip}")
        return

    if args.app_list:
        logging.debug("App list requested, displaying configured apps")
        print("Configured apps:")
        for app in APPS_CONFIG:
            print(f"  {app}")
        sys.exit(0)

    logging.debug("Starting PortRefresher")
    refresher = PortRefresher(args.refresh_seconds, args.vpn_gateway, args.app_control, args.loglevel, args.pmt_timeout)
    refresher.run()

if __name__ == "__main__":
    main()