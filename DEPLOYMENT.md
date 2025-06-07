# Blockchain Network Deployment Guide

This guide provides step-by-step instructions for deploying the energy-efficient DPoS blockchain network with 6 Raspberry Pi nodes and 2 MQTT brokers.

## Prerequisites

### For MQTT Brokers (VMs)
- Ubuntu Server 20.04 LTS or later
- 2GB RAM minimum
- 20GB storage
- Static IP addresses (192.168.1.10 and 192.168.1.11)

### For Raspberry Pi Nodes
- Raspberry Pi 4 (2GB RAM or more)
- Raspberry Pi OS (64-bit)
- MicroSD card (32GB recommended)
- Power supply
- Network connection
- `python3-dev` (required for some Python packages)

## Network Setup

1. Configure static IP addresses for all devices:
   - MQTT Broker 1: 192.168.1.10
   - MQTT Broker 2: 192.168.1.11
   - Raspberry Pi 1: 192.168.1.101
   - Raspberry Pi 2: 192.168.1.102
   - Raspberry Pi 3: 192.168.1.103
   - Raspberry Pi 4: 192.168.1.104
   - Raspberry Pi 5: 192.168.1.105
   - Raspberry Pi 6: 192.168.1.106

2. Ensure all devices can communicate with each other:
   ```bash
   ping 192.168.1.10  # From all devices
   ping 192.168.1.11  # From all devices
   ```

## MQTT Broker Deployment

1. SSH into each MQTT broker VM:
   ```bash
   ssh user@192.168.1.10  # For broker 1
   ssh user@192.168.1.11  # For broker 2
   ```

2. Clone the repository:
   ```bash
   git clone https://github.com/M-kev/iot-dpos-blockchain.git
   cd iot-dpos-blockchain
   ```

3. Make the setup script executable:
   ```bash
   chmod +x scripts/setup_broker.sh
   ```

4. Run the setup script:
   ```bash
   # On broker 1
   ./scripts/setup_broker.sh broker1

   # On broker 2
   ./scripts/setup_broker.sh broker2
   ```

5. Verify MQTT broker status:
   ```bash
   sudo systemctl status mosquitto
   ```

## Raspberry Pi Node Deployment

1. SSH into each Raspberry Pi:
   ```bash
   ssh pi@192.168.1.10X  # Where X is 1-6
   ```

2. Clone the repository:
   ```bash
   git clone https://github.com/M-kev/iot-dpos-blockchain.git
   cd iot-dpos-blockchain
   ```

3. Make the setup script executable:
   ```bash
   chmod +x scripts/setup_node.sh
   ```

4. Run the setup script for each node:
   ```bash
   # On Raspberry Pi 1
   ./scripts/setup_node.sh 1

   # On Raspberry Pi 2
   ./scripts/setup_node.sh 2

   # And so on for nodes 3-6
   ```

5. Verify node status:
   ```bash
   sudo systemctl status blockchain-node
   ```

## Testing the Deployment

1. Check MQTT broker connectivity:
   ```bash
   # On any Raspberry Pi
   mosquitto_sub -h 192.168.1.10 -p 1883 -u broker1 -P broker1pass -t 'blocks'
   mosquitto_sub -h 192.168.1.11 -p 1883 -u broker2 -P broker2pass -t 'blocks'
   ```

2. Access node dashboards:
   - Node 1: http://192.168.1.101:8001
   - Node 2: http://192.168.1.102:8002
   - Node 3: http://192.168.1.103:8003
   - Node 4: http://192.168.1.104:8004
   - Node 5: http://192.168.1.105:8005
   - Node 6: http://192.168.1.106:8006

3. Monitor node logs:
   ```bash
   sudo journalctl -u blockchain-node -f
   ```

## Troubleshooting

1. MQTT Connection Issues:
   - Check broker status: `sudo systemctl status mosquitto`
   - Verify credentials in .env file
   - Check network connectivity
   - Review broker logs: `sudo tail -f /var/log/mosquitto/mosquitto.log`

2. Node Issues:
   - Check node status: `sudo systemctl status blockchain-node`
   - Review node logs: `sudo journalctl -u blockchain-node`
   - Verify Python environment: `source venv/bin/activate && python --version`
   - Check system resources: `htop`

3. Dashboard Access Issues:
   - Verify port accessibility: `netstat -tulpn | grep 800`
   - Check firewall settings: `sudo ufw status`
   - Verify node is running: `sudo systemctl status blockchain-node`

## Maintenance

1. Updating Nodes:
   ```bash
   cd ~/blockchain_node
   git pull
   source venv/bin/activate
   pip install -r requirements.txt
   sudo systemctl restart blockchain-node
   ```

2. Updating Brokers:
   ```bash
   sudo apt-get update
   sudo apt-get upgrade mosquitto
   sudo systemctl restart mosquitto
   ```

3. Backup:
   - Regularly backup node data
   - Monitor system resources
   - Check logs for errors

## Security Notes

1. Change default passwords
2. Use SSH keys for authentication
3. Keep systems updated
4. Monitor system logs
5. Use firewall rules to restrict access 