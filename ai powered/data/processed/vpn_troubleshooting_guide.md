# VPN Connection Troubleshooting Guide

This guide assists in resolving common Virtual Private Network (VPN) connection problems.

## Basic Checks

1.  **Internet Connection:** Ensure your underlying internet connection is working correctly before attempting to connect to the VPN.
2.  **Credentials:** Double-check your username, password, and two-factor authentication (2FA) codes.
3.  **VPN Client:** Ensure the VPN client is up-to-date. Restart the VPN application entirely.

## Common Issues & Solutions

### 1. Connection Timed Out
-   **Solution:** Check if a local firewall or antivirus is blocking the VPN traffic. Try temporarily disabling it to test.
-   **Action:** Switch between available connection protocols (e.g., from OpenVPN UDP to OpenVPN TCP, or WireGuard) in the VPN client settings.

### 2. Authorization Failure
-   **Solution:** Verify your account isn't locked out due to multiple failed login attempts. Contact IT Support if your password was recently reset.

### 3. Connected but No Network Access
-   **Solution:** Look into DNS leaks or routing issues. Ensure the VPN is providing you with valid DNS servers.
-   **Action:** Disconnect the VPN, clear your DNS cache (`ipconfig /flushdns` on Windows), and reconnect.

### 4. Application Hangs/Crashes
-   **Solution:** Reinstall the VPN client or update your system's network drivers.
