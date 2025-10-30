# Network Configuration

## Updated Configuration

The `tools/config/nodes.yaml` has been updated with the correct IP addresses and ports for your blockchain network.

## Network Topology

### MQTT Broker
- **IP**: `192.168.2.11`
- **Port**: `1883`
- **Username**: `broker1`
- **Password**: `broker1pass`

### Blockchain Nodes

| Node ID | IP Address | Dashboard Port | Dashboard URL |
|---------|------------|----------------|---------------|
| pi_node_1 | 192.168.2.106 | 8001 | http://192.168.2.106:8001 |
| pi_node_2 | 192.168.2.107 | 8002 | http://192.168.2.107:8002 |
| pi_node_3 | 192.168.2.104 | 8003 | http://192.168.2.104:8003 |
| pi_node_4 | 192.168.2.102 | 8004 | http://192.168.2.102:8004 |
| pi_node_5 | 192.168.2.105 | 8005 | http://192.168.2.105:8005 |

## Verification Steps

### 1. Test MQTT Broker Connectivity

From any machine on the network:

```bash
# Install mosquitto clients if needed
sudo apt install mosquitto-clients

# Subscribe to metrics topic
mosquitto_sub -h 192.168.2.11 -p 1883 -u broker1 -P broker1pass -t 'iot/metrics' -v
```

### 2. Test Node Dashboard Connectivity

```bash
# Test each node's dashboard
curl http://192.168.2.106:8001/api/metrics  # Node 1
curl http://192.168.2.107:8002/api/metrics  # Node 2
curl http://192.168.2.104:8003/api/metrics  # Node 3
curl http://192.168.2.102:8004/api/metrics  # Node 4
curl http://192.168.2.105:8005/api/metrics  # Node 5
```

Expected response: JSON with blockchain metrics

### 3. Test CSV Export Endpoints

```bash
# Test block metrics export from Node 1
curl http://192.168.2.106:8001/api/export/block-metrics.csv

# Test transaction lifecycle export from Node 2
curl http://192.168.2.107:8002/api/export/transaction-lifecycle.csv
```

Expected response: CSV data with headers

## Running the Stress Test

Now that the configuration is correct, you can run the stress test:

```bash
cd ~/iot-dpos-blockchain/tools
./run_test_plan.sh baseline 300 5 3
```

### What the Script Will Do:

1. **Apply network profile** (baseline: 10ms delay, 2ms jitter, 0.1% loss)
2. **Generate MQTT load**:
   - Target: `192.168.2.11:1883` (MQTT broker)
   - 3 simulated nodes publishing metrics
   - 1 transaction publisher
   - Rate: 5 messages/second
   - Duration: 300 seconds (5 minutes)
3. **Collect CSV data** from all 5 nodes:
   - `http://192.168.2.106:8001/api/export/*`
   - `http://192.168.2.107:8002/api/export/*`
   - `http://192.168.2.104:8003/api/export/*`
   - `http://192.168.2.102:8004/api/export/*`
   - `http://192.168.2.105:8005/api/export/*`
4. **Generate report** with aggregated metrics
5. **Clear network impairments**

## Troubleshooting

### If CSV collection fails:

1. **Check blockchain services are running on all nodes:**
   ```bash
   ssh node@192.168.2.106 'sudo systemctl status blockchain-node'
   ssh node@192.168.2.107 'sudo systemctl status blockchain-node'
   ssh node@192.168.2.104 'sudo systemctl status blockchain-node'
   ssh node@192.168.2.102 'sudo systemctl status blockchain-node'
   ssh node@192.168.2.105 'sudo systemctl status blockchain-node'
   ```

2. **Check dashboards are accessible:**
   ```bash
   curl http://192.168.2.106:8001/api/metrics
   ```

3. **Check firewall rules:**
   ```bash
   # On each Raspberry Pi
   sudo ufw status
   # Ensure ports 8001-8005 are allowed
   ```

### If MQTT load fails:

1. **Check MQTT broker is running:**
   ```bash
   ssh node@192.168.2.11 'sudo systemctl status mosquitto'
   ```

2. **Test MQTT authentication:**
   ```bash
   mosquitto_pub -h 192.168.2.11 -u broker1 -P broker1pass -t 'test' -m 'hello'
   ```

3. **Check broker logs:**
   ```bash
   ssh node@192.168.2.11 'sudo journalctl -u mosquitto -f'
   ```

## Where to Run the Test

The `run_test_plan.sh` script should be run from:

1. **One of the Raspberry Pi nodes** (recommended)
2. **Any Linux machine on the 192.168.2.x network**
3. **Your development machine** if it's on the same network

**Do not run from the MQTT broker machine** (192.168.2.11), as applying `tc netem` will affect the broker's communication.

## Test Artifacts

Results will be saved to:
```
~/iot-dpos-blockchain/artifacts/YYYYMMDD-HHMMSS/
├── raw/
│   ├── pi_node_1-block-metrics.csv
│   ├── pi_node_1-tx-lifecycle.csv
│   ├── pi_node_2-block-metrics.csv
│   └── ...
├── merged/
│   ├── all-block-metrics.csv
│   └── all-tx-lifecycle.csv
├── report.html
└── summary.txt
```

