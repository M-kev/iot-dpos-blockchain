#!/bin/bash

# Stop the blockchain service
echo "Stopping blockchain service..."
sudo systemctl stop blockchain-node

# Remove blockchain data
echo "Removing blockchain data..."
rm -rf ~/iot-dpos-blockchain/blockchain_data
rm -rf ~/iot-dpos-blockchain/static

# Remove SQLite database if it exists
echo "Removing SQLite database..."
rm -f ~/iot-dpos-blockchain/data/blockchain.db

# Remove any temporary files
echo "Cleaning temporary files..."
rm -f ~/iot-dpos-blockchain/*.log
rm -f ~/iot-dpos-blockchain/*.pid

echo "Cleanup complete. You can now redeploy the node using setup_node.sh" 