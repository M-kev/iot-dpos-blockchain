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

REPO_URL=<your-repo-url>  # <-- Replace with your actual repo URL
REPO_DIR="$HOME/iot-dpos-blockchain"

# Clone the repository if not already present
if [ ! -d "$REPO_DIR/.git" ]; then
    git clone $REPO_URL $REPO_DIR
fi

cd $REPO_DIR

echo "Setting up Python virtual environment..."
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
sudo tee /etc/systemd/system/blockchain-node.service > /dev/null << EOF
[Unit]
Description=Blockchain Node Service
After=network.target

[Service]
User=$USER
WorkingDirectory=$HOME/iot-dpos-blockchain
Environment="PATH=$HOME/iot-dpos-blockchain/venv/bin"
ExecStart=$HOME/iot-dpos-blockchain/venv/bin/python $HOME/iot-dpos-blockchain/src/main.py
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
