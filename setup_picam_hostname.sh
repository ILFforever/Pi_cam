#!/bin/bash
# Setup script to configure Raspberry Pi with hostname 'picam' for local DNS access
# This enables access via http://picam.local

set -e

echo "=================================="
echo "Setting up PiCam Local DNS Access"
echo "=================================="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root (use sudo)"
    exit 1
fi

# 1. Check if Avahi daemon is installed
echo "[1/5] Checking Avahi installation..."
if ! command -v avahi-daemon &> /dev/null; then
    echo "Avahi not found. Installing avahi-daemon..."
    apt-get update
    apt-get install -y avahi-daemon avahi-utils
else
    echo "✓ Avahi is already installed"
fi

# 2. Set the hostname to 'picam'
echo ""
echo "[2/5] Setting hostname to 'picam'..."
CURRENT_HOSTNAME=$(hostname)
echo "Current hostname: $CURRENT_HOSTNAME"

if [ "$CURRENT_HOSTNAME" != "picam" ]; then
    # Update /etc/hostname
    echo "picam" > /etc/hostname

    # Update /etc/hosts
    sed -i "s/127.0.1.1.*/127.0.1.1\tpicam/" /etc/hosts

    # Apply hostname change
    hostnamectl set-hostname picam

    echo "✓ Hostname changed to 'picam'"
else
    echo "✓ Hostname is already set to 'picam'"
fi

# 3. Configure Avahi daemon
echo ""
echo "[3/5] Configuring Avahi daemon..."

# Ensure Avahi configuration exists
if [ ! -f /etc/avahi/avahi-daemon.conf ]; then
    echo "Creating default Avahi configuration..."
    cat > /etc/avahi/avahi-daemon.conf << 'EOF'
[server]
host-name=picam
domain-name=local
use-ipv4=yes
use-ipv6=yes
allow-interfaces=wlan0,eth0
deny-interfaces=
ratelimit-interval-usec=1000000
ratelimit-burst=1000

[wide-area]
enable-wide-area=yes

[publish]
publish-addresses=yes
publish-hinfo=yes
publish-workstation=yes
publish-domain=yes
publish-aaaa-on-ipv4=yes
publish-a-on-ipv6=no

[reflector]
enable-reflector=no

[rlimits]
rlimit-core=0
rlimit-data=4194304
rlimit-fsize=0
rlimit-nofile=768
rlimit-stack=4194304
rlimit-nproc=3
EOF
else
    # Update host-name in existing config
    sed -i "s/^#\?host-name=.*/host-name=picam/" /etc/avahi/avahi-daemon.conf
    sed -i "s/^#\?domain-name=.*/domain-name=local/" /etc/avahi/avahi-daemon.conf
    echo "✓ Updated existing Avahi configuration"
fi

# 4. Enable and start Avahi daemon
echo ""
echo "[4/5] Enabling and starting Avahi daemon..."
systemctl enable avahi-daemon
systemctl restart avahi-daemon

# Wait for service to start
sleep 2

# Check if service is running
if systemctl is-active --quiet avahi-daemon; then
    echo "✓ Avahi daemon is running"
else
    echo "✗ Warning: Avahi daemon failed to start"
    systemctl status avahi-daemon --no-pager
fi

# 5. Show network information
echo ""
echo "[5/5] Network Information"
echo "========================="

# Get IP addresses
echo "IP Addresses:"
ip -4 addr show | grep -oP '(?<=inet\s)\d+(\.\d+){3}' | grep -v '127.0.0.1' | while read ip; do
    echo "  - $ip"
done

echo ""
echo "=================================="
echo "Setup Complete!"
echo "=================================="
echo ""
echo "Your camera can now be accessed at:"
echo "  http://picam.local:5000"
echo ""
echo "Note: You may need to reboot for all changes to take effect:"
echo "  sudo reboot"
echo ""
echo "Testing mDNS resolution..."
avahi-browse -a -t -r 2>/dev/null | grep -i "picam" || echo "Run 'avahi-browse -a -t' to see all mDNS services"
echo ""
echo "From other devices on the same network, you can now use:"
echo "  - http://picam.local:5000 (for photo gallery)"
echo "  - ssh pi@picam.local (for SSH access)"
echo "  - ping picam.local (to test connectivity)"
echo ""
