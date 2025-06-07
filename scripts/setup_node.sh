#!/bin/bash

# Check if node number is provided
if [ -z "$1" ]; then
    echo "Please provide node number (1-6)"
    exit 1
fi

NODE_NUM=$1
if [ $NODE_NUM -lt 1 ] || [ $NODE_NUM -gt 6 ]; then
    echo "Node number must be between 1 and 6"
    exit 1
fi

# Create project directory
mkdir -p ~/blockchain_node
cd ~/blockchain_node

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
cat > .env << EOF
NODE_ID=pi_node_${NODE_NUM}
MQTT_BROKER_1_HOST=192.168.1.10
MQTT_BROKER_1_PORT=1883
MQTT_BROKER_1_USER=broker1
MQTT_BROKER_1_PASS=broker1pass
MQTT_BROKER_2_HOST=192.168.1.11
MQTT_BROKER_2_PORT=1883
MQTT_BROKER_2_USER=broker2
MQTT_BROKER_2_PASS=broker2pass
EOF

# Create systemd service file
sudo tee /etc/systemd/system/blockchain-node.service << EOF
[Unit]
Description=Blockchain Node Service
After=network.target

[Service]
User=$USER
WorkingDirectory=$HOME/blockchain_node
Environment="PATH=$HOME/blockchain_node/venv/bin"
ExecStart=$HOME/blockchain_node/venv/bin/python src/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd
sudo systemctl daemon-reload

# Enable and start service
sudo systemctl enable blockchain-node
sudo systemctl start blockchain-node

# Check service status
sudo systemctl status blockchain-node

echo "Raspberry Pi node setup complete!" 