# Energy-Efficient DPoS Blockchain for IoT

This project implements a Delegated Proof of Stake (DPoS) blockchain system optimized for IoT devices, particularly Raspberry Pi. The system uses MQTT for device communication and implements various energy optimization techniques.

## Features

- Delegated Proof of Stake consensus mechanism
- MQTT-based device communication
- Energy monitoring and optimization
- Raspberry Pi specific optimizations
- Real-time block validation and propagation
- Energy-efficient transaction processing

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

## Energy Efficiency Features

- Dynamic block time adjustment based on network load
- Optimized consensus mechanism for low-power devices
- Efficient transaction validation
- Smart resource allocation
- Power-aware scheduling

## License

MIT License 