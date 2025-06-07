#!/bin/bash

# Install Mosquitto MQTT broker
sudo apt-get update
sudo apt-get install -y mosquitto mosquitto-clients

# Create configuration directory
sudo mkdir -p /etc/mosquitto/conf.d

# Create broker configuration
sudo tee /etc/mosquitto/conf.d/broker.conf << EOF
listener 1883
allow_anonymous false
password_file /etc/mosquitto/passwd
EOF

# Create password file
sudo touch /etc/mosquitto/passwd

# Set broker credentials
if [ "$1" == "broker1" ]; then
    sudo mosquitto_passwd -b /etc/mosquitto/passwd broker1 broker1pass
elif [ "$1" == "broker2" ]; then
    sudo mosquitto_passwd -b /etc/mosquitto/passwd broker2 broker2pass
else
    echo "Please specify broker1 or broker2"
    exit 1
fi

# Set proper permissions
sudo chown -R mosquitto:mosquitto /etc/mosquitto

# Restart Mosquitto service
sudo systemctl restart mosquitto

# Enable Mosquitto to start on boot
sudo systemctl enable mosquitto

# Verify service status
sudo systemctl status mosquitto

echo "MQTT broker setup complete!" 