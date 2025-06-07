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

REPO_URL=https://github.com/M-kev/iot-dpos-blockchain.git  # <-- Replace with your actual repo URL
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

# Ensure static directory exists for dashboard
mkdir -p static

# Create .env file

# Create systemd service file
sudo tee /etc/systemd/system/blockchain-node.service > /dev/null << EOF
[Unit]
Description=Blockchain Node Service
After=network.target

[Service]
User=$USER
WorkingDirectory=$HOME/iot-dpos-blockchain
Environment="PATH=$HOME/iot-dpos-blockchain/venv/bin:/usr/bin"
Environment="PYTHONPATH=$HOME/iot-dpos-blockchain/src"
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
