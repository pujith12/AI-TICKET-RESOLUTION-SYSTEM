# Network Connectivity Troubleshooting Guide

This guide covers common network issues and how to resolve them.

## Basic Checks
1. **Physical Connection:** Ensure Ethernet cables are securely connected. For Wi-Fi, ensure the adapter is enabled and connected to the correct SSID.
2. **IP Configuration:** Run `ipconfig` (Windows) or `ifconfig` / `ip addr` (Linux/Mac) to ensure you have a valid IP address and not an APIPA address (169.254.x.x).
3. **Ping Tests:**
   - Ping the default gateway.
   - Ping an external IP (e.g., `8.8.8.8` for Google DNS).
   - Ping a domain name (e.g., `google.com`) to verify DNS is working.

## Advanced Steps
1. **DNS Flush:** If you can ping by IP but not domain, flush DNS.
   - Windows: `ipconfig /flushdns`
   - Mac: `sudo dscacheutil -flushcache; sudo killall -HUP mDNSResponder`
2. **Network Reset:** Reset the network stack if issues persist.
   - Windows: `netsh winsock reset`
3. **Proxy/VPN:** Verify if a proxy or VPN is interfering with the connection and try toggling it.
