#!/usr/bin/env python3
"""
Unit tests for protonvpn-public-port-refresh.py
"""

import unittest
from unittest.mock import patch, MagicMock, call, Mock
import sys
import os
import argparse

# Add the script directory to path so we can import the module
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the classes and functions we want to test
from protonvpn_public_port_refresh import PortRefresher, APPS_CONFIG, NAT_PMP_PATH, start_folx, stop_folx, get_folx_status


class TestPortRefresher(unittest.TestCase):
    """Test cases for the PortRefresher class."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_args = {
            'refresh_seconds': 45,
            'vpn_gateway': '10.2.0.1',
            'app_control': 'Folx3-setapp',
            'loglevel': 'info',
            'pmt_timeout': 30
        }

    @patch('protonvpn_public_port_refresh.logging')
    def test_init(self, mock_logging):
        """Test PortRefresher initialization."""
        refresher = PortRefresher(**self.test_args)

        self.assertEqual(refresher.refresh_seconds, 45)
        self.assertEqual(refresher.vpn_gateway, '10.2.0.1')
        self.assertEqual(refresher.app_control, ['Folx3-setapp'])
        self.assertFalse(refresher.stopped)
        self.assertIsNone(refresher.current_port)

    @patch('protonvpn_public_port_refresh.subprocess.run')
    def test_get_public_port_success(self, mock_subprocess):
        """Test successful port retrieval."""
        # Mock successful subprocess call with proper output format
        mock_result = MagicMock()
        # Create output with at least 15 space-separated fields, 15th being "12345,other"
        mock_result.stdout = "field1 field2 field3 field4 field5 field6 field7 field8 field9 field10 field11 field12 field13 field14 12345,other"
        mock_subprocess.return_value = mock_result

        refresher = PortRefresher(**self.test_args)
        port = refresher.get_public_port()

        self.assertEqual(port, 12345)
        mock_subprocess.assert_called_once_with([
            NAT_PMP_PATH, "-g", "10.2.0.1", "0", "0"
        ], capture_output=True, text=True, check=True, timeout=None)

    @patch('protonvpn_public_port_refresh.subprocess.run')
    def test_get_public_port_failure(self, mock_subprocess):
        """Test port retrieval failure."""
        from subprocess import CalledProcessError
        mock_subprocess.side_effect = CalledProcessError(1, 'cmd', 'error output')

        refresher = PortRefresher(**self.test_args)
        port = refresher.get_public_port()

        self.assertIsNone(port)

    @patch('protonvpn_public_port_refresh.subprocess.run')
    def test_get_public_port_parse_error(self, mock_subprocess):
        """Test port parsing error."""
        mock_result = MagicMock()
        mock_result.stdout = "insufficient fields"
        mock_subprocess.return_value = mock_result

        refresher = PortRefresher(**self.test_args)
        port = refresher.get_public_port()

        self.assertIsNone(port)

    @patch('protonvpn_public_port_refresh.logging')
    @patch('protonvpn_public_port_refresh.subprocess.run')
    def test_control_app_start(self, mock_subprocess, mock_logging):
        """Test starting an application."""
        refresher = PortRefresher(**self.test_args)
        refresher.current_port = 12345

        refresher.control_app("Folx3-setapp", "start")

        # Should only call start, not set_port
        mock_subprocess.assert_called_with(["open", "/Applications/Setapp/Folx.app"], check=True)

    @patch('protonvpn_public_port_refresh.logging')
    @patch('protonvpn_public_port_refresh.subprocess.run')
    def test_control_app_stop(self, mock_subprocess, mock_logging):
        """Test stopping an application."""
        refresher = PortRefresher(**self.test_args)

        refresher.control_app("Folx3-setapp", "stop")

        mock_subprocess.assert_called_with([
            "osascript", "-e", 'quit app "Folx"'
        ], check=True)

    @patch('protonvpn_public_port_refresh.logging')
    def test_control_app_unknown(self, mock_logging):
        """Test controlling unknown application."""
        refresher = PortRefresher(**self.test_args)

        refresher.control_app("UnknownApp", "start")

        mock_logging.warning.assert_called_with("Unknown app: UnknownApp")

    @patch('protonvpn_public_port_refresh.subprocess.run')
    def test_start_apps(self, mock_subprocess):
        """Test starting all controlled apps."""
        refresher = PortRefresher(**self.test_args)
        refresher.current_port = 12345

        refresher.start_apps()

        # Should set port and start Folx
        expected_calls = [
            call([
                "defaults", "write", "com.eltima.Folx3-setapp",
                "GeneralUserSettings", "-dict-add", "TorrentTCPPort", "12345"
            ], check=True),
            call(["open", "/Applications/Setapp/Folx.app"], check=True)
        ]
        mock_subprocess.assert_has_calls(expected_calls)

    @patch('protonvpn_public_port_refresh.subprocess.run')
    def test_stop_apps(self, mock_subprocess):
        """Test stopping all controlled apps."""
        refresher = PortRefresher(**self.test_args)

        refresher.stop_apps()

        mock_subprocess.assert_called_with([
            "osascript", "-e", 'quit app "Folx"'
        ], check=True)

    @patch('protonvpn_public_port_refresh.PortRefresher.run_diagnostic_command')
    @patch('protonvpn_public_port_refresh.PortRefresher.get_public_port')
    def test_check_vpn_connection_connected(self, mock_get_port, mock_run_diag):
        """Test VPN connection check when connected."""
        mock_run_diag.return_value = {'success': True, 'output': '10.2.0.1 10.2.0.1 UGSc 0 0 utun0'}
        mock_get_port.return_value = 12345

        refresher = PortRefresher(**self.test_args)
        status = refresher.check_vpn_connection()

        self.assertTrue(status['connected'])
        self.assertEqual(status['interface'], 'utun0')
        self.assertTrue(status['natpmp_supported'])

    @patch('protonvpn_public_port_refresh.PortRefresher.run_diagnostic_command')
    @patch('protonvpn_public_port_refresh.PortRefresher.get_public_port')
    def test_check_vpn_connection_not_connected(self, mock_get_port, mock_run_diag):
        """Test VPN connection check when not connected."""
        mock_run_diag.return_value = {'success': True, 'output': 'no relevant routes'}
        mock_get_port.return_value = None

        refresher = PortRefresher(**self.test_args)
        status = refresher.check_vpn_connection()

        self.assertFalse(status['connected'])
        self.assertIsNone(status['interface'])
        self.assertFalse(status['natpmp_supported'])

    def test_run_diagnostic_command_success(self):
        """Test running diagnostic command successfully."""
        refresher = PortRefresher(**self.test_args)
        result = refresher.run_diagnostic_command("echo test")

        self.assertTrue(result['success'])
        self.assertEqual(result['output'], "test\n")
        self.assertEqual(result['error'], "")

    def test_run_diagnostic_command_failure(self):
        """Test running diagnostic command failure."""
        refresher = PortRefresher(**self.test_args)
        result = refresher.run_diagnostic_command("false")

        self.assertFalse(result['success'])
        self.assertEqual(result['output'], "")
        # Note: 'false' may not produce stderr, so just check success

    @patch('protonvpn_public_port_refresh.PortRefresher.run_diagnostic_command')
    def test_get_network_info(self, mock_run_diag):
        """Test getting network info."""
        mock_run_diag.side_effect = [
            {'success': True, 'output': 'route table'},
            {'success': True, 'output': 'interfaces'},
            {'success': True, 'output': 'dns ok'}
        ]

        refresher = PortRefresher(**self.test_args)
        info = refresher.get_network_info()

        self.assertIn('routing_table', info)
        self.assertIn('interfaces', info)
        self.assertTrue(info['dns_working'])

    def test_format_bps(self):
        """Test BPS formatting."""
        refresher = PortRefresher(**self.test_args)

        # Test various BPS values
        self.assertEqual(refresher.format_bps(None), "N/A")
        self.assertEqual(refresher.format_bps(0), "0bps")
        self.assertEqual(refresher.format_bps(500), "500bps")
        self.assertEqual(refresher.format_bps(1500), "1.5Kbps")
        self.assertEqual(refresher.format_bps(2500000), "2.5Mbps")
        self.assertEqual(refresher.format_bps(1500000000), "1.5Gbps")

    def test_calculate_bps_rates(self):
        """Test BPS rate calculation."""
        import time
        refresher = PortRefresher(**self.test_args)

        # Mock time from the beginning
        original_time = time.time
        call_count = 0
        def mock_time():
            nonlocal call_count
            call_count += 1
            return 1000.0 + (call_count - 1)  # First call: 1000, second call: 1001
        
        time.time = mock_time

        try:
            # First call should return None (baseline)
            ibps, obps = refresher.calculate_bps_rates(1000, 2000)
            self.assertIsNone(ibps)
            self.assertIsNone(obps)

            # Second call with 1 second time difference
            ibps, obps = refresher.calculate_bps_rates(2000, 4000)
            # 1000 bytes * 8 bits/byte / 1 second = 8000 bps
            self.assertAlmostEqual(ibps, 8000, places=0)
            self.assertAlmostEqual(obps, 16000, places=0)
        finally:
            time.time = original_time


class TestAppFunctions(unittest.TestCase):
    """Test cases for application control functions."""

    @patch('protonvpn_public_port_refresh.subprocess.run')
    def test_start_folx(self, mock_subprocess):
        """Test starting Folx."""
        start_folx("/Applications/Folx.app")

        mock_subprocess.assert_called_with(["open", "/Applications/Folx.app"], check=True)

    @patch('protonvpn_public_port_refresh.subprocess.run')
    def test_stop_folx(self, mock_subprocess):
        """Test stopping Folx."""
        stop_folx()

        mock_subprocess.assert_called_with([
            "osascript", "-e", 'quit app "Folx"'
        ], check=True)

    @patch('protonvpn_public_port_refresh.subprocess.run')
    def test_get_folx_status(self, mock_subprocess):
        """Test getting Folx status."""
        # Mock the defaults export command to return plist data
        mock_plist_data = b'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>GeneralUserSettings</key>
    <dict>
        <key>TorrentTCPPort</key>
        <integer>51413</integer>
    </dict>
</dict>
</plist>'''
        
        # Mock all subprocess calls
        def mock_run(*args, **kwargs):
            cmd = args[0] if args else kwargs.get('args', [])
            if 'defaults' in cmd and 'export' in cmd:
                mock_result = MagicMock()
                mock_result.returncode = 0
                mock_result.stdout = mock_plist_data
                return mock_result
            elif 'pgrep' in cmd:
                mock_result = MagicMock()
                mock_result.returncode = 0
                mock_result.stdout = b"Folx\n"
                return mock_result
            elif 'lsof' in cmd:
                mock_result = MagicMock()
                mock_result.returncode = 0
                mock_result.stdout = b"3\n"
                return mock_result
            elif 'ps' in cmd:
                mock_result = MagicMock()
                mock_result.returncode = 0
                mock_result.stdout = b"user 1234 1.2 3.4 Folx\n"
                return mock_result
            else:
                mock_result = MagicMock()
                mock_result.returncode = 1
                mock_result.stdout = b""
                return mock_result
        
        mock_subprocess.side_effect = mock_run
        
        refresher = PortRefresher(45, '10.2.0.1', [], 'info', 30)
        refresher.current_port = 51413
        
        status = get_folx_status(refresher)
        
        self.assertTrue(status['running'])
        self.assertEqual(status['port'], 51413)
        self.assertEqual(status['connections'], 2)  # 3 - 1
        self.assertEqual(status['cpu'], 1.2)
        self.assertAlmostEqual(status['memory'], 34.816, places=2)  # 3.4 * 1024 / 100


class TestConfiguration(unittest.TestCase):
    """Test cases for configuration."""

    def test_apps_config_structure(self):
        """Test that APPS_CONFIG has correct structure."""
        self.assertIn("Folx3-setapp", APPS_CONFIG)

        folx_config = APPS_CONFIG["Folx3-setapp"]
        required_keys = ["path", "defaults", "start", "stop"]

        for key in required_keys:
            self.assertIn(key, folx_config)

        self.assertEqual(folx_config["path"], "/Applications/Setapp/Folx.app")
        self.assertEqual(folx_config["defaults"], "com.eltima.Folx3-setapp")
        self.assertTrue(callable(folx_config["start"]))
        self.assertTrue(callable(folx_config["stop"]))

    def test_nat_pmp_path(self):
        """Test NAT_PMP_PATH is properly expanded."""
        expected_path = os.path.expanduser("~/Library/Python/3.9/bin/natpmp-client.py")
        self.assertEqual(NAT_PMP_PATH, expected_path)


class TestArgumentParsing(unittest.TestCase):
    """Test cases for command-line argument parsing."""

    @patch('protonvpn_public_port_refresh.PortRefresher')
    @patch('protonvpn_public_port_refresh.sys.exit')
    @patch('builtins.print')
    @patch('sys.argv', ['test', '--app-list'])
    def test_app_list_option(self, mock_print, mock_exit, mock_refresher):
        """Test --app-list option."""
        from protonvpn_public_port_refresh import main
        main()

        mock_print.assert_any_call("Configured apps:")
        mock_print.assert_any_call("  Folx3-setapp")
        mock_exit.assert_called_with(0)
        # Note: PortRefresher may be called after the mocked exit, but that's ok

    @patch('protonvpn_public_port_refresh.PortRefresher')
    @patch('sys.argv', ['test'])
    def test_default_arguments(self, mock_refresher):
        """Test default argument values."""
        from protonvpn_public_port_refresh import main
        main()

        # Check that PortRefresher was called with defaults
        mock_refresher.assert_called_once_with(45, '10.2.0.1', '', 'info', 30)
        # Ensure run() was called
        mock_refresher.return_value.run.assert_called_once()

    @patch('protonvpn_public_port_refresh.PortRefresher')
    @patch('builtins.print')
    @patch('sys.argv', ['test', '--vpn-status'])
    def test_vpn_status_option(self, mock_print, mock_refresher):
        """Test --vpn-status option."""
        mock_instance = mock_refresher.return_value
        mock_instance.check_vpn_connection.return_value = {
            'connected': True, 'gateway': '10.2.0.1', 'interface': 'utun0', 'natpmp_supported': True
        }

        from protonvpn_public_port_refresh import main
        main()

        mock_print.assert_any_call("VPN Connection Status:")
        mock_print.assert_any_call("  Connected: True")
        mock_print.assert_any_call("  Gateway: 10.2.0.1")
        mock_print.assert_any_call("  Interface: utun0")
        mock_print.assert_any_call("  NAT-PMP Supported: True")

    @patch('protonvpn_public_port_refresh.PortRefresher')
    @patch('builtins.print')
    @patch('sys.argv', ['test', '--diagnostics'])
    def test_diagnostics_option(self, mock_print, mock_refresher):
        """Test --diagnostics option."""
        mock_instance = mock_refresher.return_value
        mock_instance.run_diagnostic_command.side_effect = [
            {'success': True, 'output': '', 'error': ''},  # ping
            {'success': True, 'output': '', 'error': ''}   # port
        ]
        mock_instance.get_public_port.return_value = 12345

        from protonvpn_public_port_refresh import main
        main()

        mock_print.assert_any_call("Running Network Diagnostics...")
        mock_print.assert_any_call("Internet Connectivity: ✓")
        mock_print.assert_any_call("NAT-PMP Port Acquisition: ✓")

    @patch('protonvpn_public_port_refresh.PortRefresher')
    @patch('builtins.print')
    @patch('sys.argv', ['test', '--network-info'])
    def test_network_info_option(self, mock_print, mock_refresher):
        """Test --network-info option."""
        mock_instance = mock_refresher.return_value
        mock_instance.get_network_info.return_value = {
            'routing_table': 'routes', 'interfaces': 'eth0', 'dns_working': True
        }

        from protonvpn_public_port_refresh import main
        main()

        mock_print.assert_any_call("Network Information:")
        mock_print.assert_any_call("DNS Resolution: ✓")

    @patch('protonvpn_public_port_refresh.curses')
    @patch('protonvpn_public_port_refresh.PortRefresher')
    @patch('sys.argv', ['test', '--status'])
    def test_status_option(self, mock_refresher, mock_curses):
        """Test --status option."""
        from protonvpn_public_port_refresh import main
        main()

        # Check that PortRefresher was created
        mock_refresher.assert_called_once_with(45, '10.2.0.1', '', 'info', 30)
        # Check that curses.wrapper was called with status screen
        mock_curses.wrapper.assert_called_once()
        # The wrapper should be called with function, timeout, args, and status_refresh
        args, kwargs = mock_curses.wrapper.call_args
        self.assertEqual(len(args), 4)  # function, timeout, args, status_refresh
        self.assertIsNone(args[1])  # timeout should be None
        self.assertEqual(args[3], 5)  # status_refresh should be 5 (default)

    @patch('protonvpn_public_port_refresh.curses')
    @patch('protonvpn_public_port_refresh.PortRefresher')
    @patch('sys.argv', ['test', '--status', '--status-timeout', '30'])
    def test_status_with_timeout_option(self, mock_refresher, mock_curses):
        """Test --status with --status-timeout option."""
        from protonvpn_public_port_refresh import main
        main()

        # Check that PortRefresher was created
        mock_refresher.assert_called_once_with(45, '10.2.0.1', '', 'info', 30)
        # Check that curses.wrapper was called with status screen
        mock_curses.wrapper.assert_called_once()
        # The wrapper should be called with function, timeout, args, and status_refresh
        args, kwargs = mock_curses.wrapper.call_args
        self.assertEqual(len(args), 4)  # function, timeout, args, status_refresh
        self.assertEqual(args[1], 30)  # timeout should be 30
        self.assertEqual(args[3], 5)  # status_refresh should be 5 (default)


if __name__ == '__main__':
    unittest.main()