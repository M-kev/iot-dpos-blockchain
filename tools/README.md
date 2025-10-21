## Benchmark & Scalability Toolkit

This folder contains a reproducible test plan to stress the IoT DPoS blockchain and generate a merged report. It includes network impairment profiles, an MQTT load generator, CSV collectors, and a report generator.

### Contents
- `config/nodes.yaml` — node list, broker and topics
- `netem/netem.sh` — apply/clear latency/jitter/loss profiles
- `load/mqtt_load.py` — synthetic metrics + transaction load via MQTT
- `collect/pull_csvs.py` — pulls CSVs from each node dashboard
- `report/generate_report.py` — merges CSVs and outputs KPIs + HTML
- `run_test_plan.sh` — orchestrates a full test run

### Prerequisites
1) Python deps (from repo root):
```
pip install -r requirements.txt
```
2) System tools:
- `tc`/`netem` (Linux):
```
sudo apt-get update && sudo apt-get install -y iproute2
```
- `yq` (for YAML reads in the orchestrator):
```
sudo snap install yq
# or see https://github.com/mikefarah/yq for other install methods
```
3) Make scripts executable (once):
```
chmod +x tools/netem/netem.sh tools/run_test_plan.sh
```

### Configure Nodes & Broker
Edit `tools/config/nodes.yaml` to match your deployment (IPs and dashboard ports):
```
nodes:
  - id: pi_node_1
    ip: 192.168.2.11
    dashboard_port: 8081
  # ...
mqtt:
  host: 192.168.2.10
  port: 1883
  username: broker1
  password: broker1pass
topics:
  metrics: iot/metrics
  transactions: iot/transactions
```

### Quick Start (Full Orchestrated Run)
From repo root:
```
./tools/run_test_plan.sh <profile> <duration_sec> <msgs_per_sec_per_publisher> <num_sim_nodes>

# Examples
./tools/run_test_plan.sh baseline 300 20 10
./tools/run_test_plan.sh moderate 600 15 25
./tools/run_test_plan.sh harsh 120 80 10
```
- Profiles: `baseline` | `moderate` | `harsh` | `clear`
- The script: applies netem → runs MQTT load → collects CSVs → merges and writes a report → clears netem

Artifacts are written to:
```
artifacts/<timestamp>/
  raw/       # per-node CSVs
  merged/    # merged CSVs + kpis.csv
  report.html
```

### What Is Measured
- Block metrics: interval, consensus time, power usage (from `block_metrics` table)
- Tx lifecycle: received vs. included timestamps and latency (from `transaction_lifecycle`)
- KPIs: blocks_total, block_interval_avg/p95, consensus_time_avg, energy_cumulative,
  tx_latency_avg/p95, tx_pending, tx_total

### Run Components Manually
1) Apply (or clear) a network profile:
```
tools/netem/netem.sh eth0 moderate
tools/netem/netem.sh eth0 clear
```
2) Start load only:
```
python3 tools/load/mqtt_load.py \
  --host 192.168.2.10 --port 1883 \
  --metrics_topic iot/metrics --tx_topic iot/transactions \
  --username broker1 --password broker1pass \
  --nodes 10 --rate 20 --duration 300
```
3) Collect CSVs from nodes listed in `nodes.yaml`:
```
python3 tools/collect/pull_csvs.py --config tools/config/nodes.yaml --out artifacts/raw
```
4) Merge + generate report:
```
python3 tools/report/generate_report.py --in artifacts/raw --out artifacts
```

### Tips & Troubleshooting
- Ensure each node dashboard is reachable at `http://<ip>:<port>/api/export/...`
- If a run is interrupted, always clear shaping:
```
tools/netem/netem.sh eth0 clear
```
- Time sync matters for latency: run NTP/chrony on all nodes
- Broker auth must match `nodes.yaml` credentials
- To increase drain rate of pending TXs during tests, you can raise per-block TX limit in the node code (not required for this toolkit)

### Extending
- Add more profiles to `netem.sh`
- Replace the Python load with `emqtt-bench` or HiveMQ `mqtt-benchmark` if higher throughput is desired
- Enhance `generate_report.py` to plot charts (matplotlib/plotly) or export to Markdown/PDF


