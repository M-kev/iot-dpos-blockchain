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

# Set the node ID based on the node number
NODE_ID="pi_node_$NODE_NUM"
echo "Setting up node: $NODE_ID"

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

# Create necessary directories
mkdir -p ~/iot-dpos-blockchain/blockchain_data
mkdir -p ~/iot-dpos-blockchain/static
mkdir -p ~/iot-dpos-blockchain/data  # For SQLite database

# Set proper permissions
chmod -R 755 ~/iot-dpos-blockchain
chown -R $USER:$USER ~/iot-dpos-blockchain

# Ensure the data directory is writable
chmod 777 ~/iot-dpos-blockchain/data

# Create an empty database file to ensure proper permissions
touch ~/iot-dpos-blockchain/data/blockchain.db
chmod 666 ~/iot-dpos-blockchain/data/blockchain.db

# Create .env file with the correct NODE_ID
echo "Creating .env file with NODE_ID=$NODE_ID"
cat > ~/iot-dpos-blockchain/.env << EOF
NODE_ID=$NODE_ID
EOF

# Create systemd service file
sudo tee /etc/systemd/system/blockchain-node.service > /dev/null << EOF
[Unit]
Description=Blockchain Node Service
After=network.target

[Service]
User=$USER
WorkingDirectory=$HOME/iot-dpos-blockchain
Environment="PATH=$HOME/iot-dpos-blockchain/venv/bin:/usr/bin"
Environment="PYTHONPATH=$HOME/iot-dpos-blockchain:$HOME/iot-dpos-blockchain/src"
Environment="NODE_ID=$NODE_ID"
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

echo "Raspberry Pi node setup complete for $NODE_ID!" 
