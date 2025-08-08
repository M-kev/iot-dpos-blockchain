# Energy-Efficient DPoS Blockchain for IoT

This project implements a Delegated Proof of Stake (DPoS) blockchain system optimized for IoT devices, particularly Raspberry Pi. The system uses MQTT for device communication and implements various energy optimization techniques.

## Features

- Delegated Proof of Stake consensus mechanism
- MQTT-based device communication
- Energy monitoring and optimization
- Raspberry Pi specific optimizations
- Real-time block validation and propagation
- Energy-efficient transaction processing
- Analytics export (CSV) for blocks and transaction lifecycles

## Architecture

The system consists of the following components:

1. **Blockchain Core**
   - DPoS consensus implementation
   - Block creation and validation
   - Transaction processing
   - Energy monitoring

2. **MQTT Communication Layer**
   - Device discovery and registration
   - Block propagation
   - Transaction broadcasting
   - Network status monitoring

3. **Energy Optimization**
   - Dynamic power management
   - Sleep mode optimization
   - Resource usage monitoring
   - Performance metrics

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Configure environment variables:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

3. Start the blockchain node:
   ```bash
   python src/main.py
   ```

## Project Structure

```
├── src/
│   ├── blockchain/         # Core blockchain implementation
│   ├── mqtt/              # MQTT communication layer
│   ├── energy/            # Energy monitoring and optimization
│   └── utils/             # Utility functions
├── tests/                 # Test suite
├── config/               # Configuration files
└── docs/                # Documentation
```

## Analytics Export (CSV)
The dashboard exposes CSV endpoints for offline analysis.

- Download per-block metrics (block intervals, consensus time, power usage):
  ```bash
  curl -s "http://<NODE_IP>:<DASHBOARD_PORT>/api/export/block-metrics.csv" -o block-metrics.csv
  ```

- Download transaction lifecycle data (received vs included times):
  ```bash
  curl -s "http://<NODE_IP>:<DASHBOARD_PORT>/api/export/transaction-lifecycle.csv" -o transaction-lifecycle.csv
  ```

Replace `<NODE_IP>` with the node's IP (e.g., 192.168.2.11) and `<DASHBOARD_PORT>` with the node's configured dashboard port (see `config/network_config.py`).

The CSVs can be opened in Excel, LibreOffice, or analyzed in Python/R.

## Energy Efficiency Features

- Dynamic block time adjustment based on network load
- Optimized consensus mechanism for low-power devices
- Efficient transaction validation
- Smart resource allocation
- Power-aware scheduling

## License

MIT License 