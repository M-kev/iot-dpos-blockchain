from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, StreamingResponse
from typing import Dict, Any, List
import json
import os
import csv
import io
from .metrics import BlockchainMetrics
from consensus.dpos import DPoS # Import DPoS to access its validator stats

app = FastAPI(title="Blockchain Dashboard")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global variable for the metrics instance, to be set by main.py
metrics: BlockchainMetrics = None

def set_metrics_instance(metrics_obj: BlockchainMetrics):
    global metrics
    metrics = metrics_obj

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def get_dashboard():
    """Serve the dashboard HTML."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Blockchain Dashboard</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <style>
            .metric-card {
                margin-bottom: 20px;
            }
            .chart-container {
                position: relative;
                height: 300px;
                margin-bottom: 20px;
            }
            .node-card .card-body {
                padding: 10px;
            }
            .node-card .card-text {
                margin-bottom: 5px;
            }
            .node-list-container {
                max-height: 400px;
                overflow-y: auto;
                border: 1px solid #e0e0e0;
                padding: 10px;
                border-radius: 5px;
            }
        </style>
    </head>
    <body>
        <div class="container mt-4">
            <h1 class="mb-4">Blockchain Dashboard</h1>
            
            <div class="row">
                <div class="col-md-6">
                    <div class="card metric-card">
                        <div class="card-body">
                            <h5 class="card-title">Consensus Protocol</h5>
                            <p class="card-text" id="consensus-protocol">DPoS</p>
                        </div>
                    </div>
                </div>
                <div class="col-md-6">
                    <div class="card metric-card">
                        <div class="card-body">
                            <h5 class="card-title">Overall Power Usage</h5>
                            <p class="card-text" id="overall-power-usage">Loading...</p>
                        </div>
                    </div>
                </div>
            </div>

            <div class="row">
                <div class="col-md-6">
                    <div class="card metric-card">
                        <div class="card-body">
                            <h5 class="card-title">Current Block Count</h5>
                            <p class="card-text" id="block-count">Loading...</p>
                        </div>
                    </div>
                </div>
                <div class="col-md-6">
                    <div class="card metric-card">
                        <div class="card-body">
                            <h5 class="card-title">Blockchain Size</h5>
                            <p class="card-text" id="blockchain-size">Loading...</p>
                        </div>
                    </div>
                </div>
            </div>

            <div class="row">
                <div class="col-md-6">
                    <div class="card metric-card">
                        <div class="card-body">
                            <h5 class="card-title">Current Validator</h5>
                            <p class="card-text" id="current-validator">Loading...</p>
                        </div>
                    </div>
                </div>
            </div>

            <div class="row">
                <div class="col-md-12">
                    <div class="card metric-card">
                        <div class="card-body">
                            <h5 class="card-title">All Validators and Stakes</h5>
                            <div class="node-list-container" id="validators-list">
                                <!-- Validators will be rendered here -->
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <h2 class="mt-4 mb-3">Individual Node Metrics</h2>
            <div class="row" id="individual-node-metrics-container">
                <!-- Individual node cards will be rendered here -->
            </div>

            <h2 class="mt-4 mb-3">Blockchain Metrics Trends</h2>
            <div class="row">
                <div class="col-md-6">
                    <div class="card metric-card">
                        <div class="card-body">
                            <h5 class="card-title">Transactions per Second (TPS)</h5>
                            <div class="chart-container">
                                <canvas id="tps-chart"></canvas>
                            </div>
                        </div>
                    </div>
                </div>
                <div class="col-md-6">
                    <div class="card metric-card">
                        <div class="card-body">
                            <h5 class="card-title">Consensus Time</h5>
                            <div class="chart-container">
                                <canvas id="consensus-chart"></canvas>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <div class="row">
                <div class="col-md-6">
                    <div class="card metric-card">
                        <div class="card-body">
                            <h5 class="card-title">Block Intervals</h5>
                            <div class="chart-container">
                                <canvas id="block-interval-chart"></canvas>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <script>
            // Chart instances (re-initialize if not already done)
            let tpsChart, consensusChart, blockIntervalChart;

            function initializeCharts() {
                tpsChart = new Chart(document.getElementById('tps-chart'), {
                    type: 'line',
                    data: {
                        labels: [],
                        datasets: [{
                            label: 'TPS',
                            data: [],
                            borderColor: 'rgb(75, 192, 192)',
                            tension: 0.1
                        }]
                    }
                });

                consensusChart = new Chart(document.getElementById('consensus-chart'), {
                    type: 'line',
                    data: {
                        labels: [],
                        datasets: [{
                            label: 'Consensus Time (ms)',
                            data: [],
                            borderColor: 'rgb(255, 99, 132)',
                            tension: 0.1
                        }]
                    }
                });

                blockIntervalChart = new Chart(document.getElementById('block-interval-chart'), {
                    type: 'line',
                    data: {
                        labels: [],
                        datasets: [{
                            label: 'Block Interval (s)',
                            data: [],
                            borderColor: 'rgb(153, 102, 255)',
                            tension: 0.1
                        }]
                    }
                });
            }

            // Call initializeCharts once DOM is ready
            document.addEventListener('DOMContentLoaded', initializeCharts);

            function updateMetrics() {
                fetch('/api/metrics')
                    .then(response => response.json())
                    .then(data => {
                        // Overall Metrics
                        document.getElementById('overall-power-usage').textContent = 
                            `Cumulative Mining: ${data.power_metrics.total_power.toFixed(2)}W`;
                        document.getElementById('block-count').textContent = data.blockchain_metrics.total_blocks;
                        document.getElementById('blockchain-size').textContent = 
                            `${(data.blockchain_size / (1024 * 1024)).toFixed(2)} MB`; // Convert bytes to MB
                        document.getElementById('current-validator').textContent = data.current_elected_validator || 'N/A';

                        // Update Validators List
                        const validatorsList = document.getElementById('validators-list');
                        validatorsList.innerHTML = ''; // Clear previous
                        const sortedValidators = Object.entries(data.all_validators_metrics)
                                                    .sort(([, stakeA], [, stakeB]) => stakeB - stakeA);
                        if (sortedValidators.length > 0) {
                            sortedValidators.forEach(([nodeId, stake]) => {
                                const p = document.createElement('p');
                                p.textContent = `${nodeId}: ${stake.toFixed(2)} stake`;
                                validatorsList.appendChild(p);
                            });
                        } else {
                            validatorsList.textContent = 'No validators found.';
                        }

                        // Update Individual Node Metrics
                        const individualNodeMetricsContainer = document.getElementById('individual-node-metrics-container');
                        individualNodeMetricsContainer.innerHTML = ''; // Clear previous
                        for (const nodeId in data.system_metrics) {
                            const nodeData = data.system_metrics[nodeId];
                            const colDiv = document.createElement('div');
                            colDiv.className = 'col-md-4';
                            colDiv.innerHTML = `
                                <div class="card metric-card node-card">
                                    <div class="card-body">
                                        <h6 class="card-title">${nodeId}</h6>
                                        <p class="card-text">CPU: ${nodeData.cpu_percent.toFixed(1)}%</p>
                                        <p class="card-text">Mem: ${nodeData.memory_percent.toFixed(1)}%</p>
                                        <p class="card-text">Temp: ${nodeData.temperature.toFixed(1)}°C</p>
                                        <p class="card-text">Power: ${nodeData.power_usage.toFixed(2)}W</p>
                                        <p class="card-text">Blocks: ${nodeData.block_count}</p>
                                        <p class="card-text">Pending TXs: ${nodeData.pending_transactions}</p>
                                        <p class="card-text">Stake: ${data.all_validators_metrics[nodeId] || 0}</p>
                                    </div>
                                </div>
                            `;
                            individualNodeMetricsContainer.appendChild(colDiv);
                        }

                        // Update Charts (existing logic, simplified as all data comes from single fetch)
                        const timestamp = new Date().toLocaleTimeString();
                        
                        // TPS Chart
                        tpsChart.data.labels.push(timestamp);
                        tpsChart.data.datasets[0].data.push(data.blockchain_metrics.tps);
                        if (tpsChart.data.labels.length > 20) {
                            tpsChart.data.labels.shift();
                            tpsChart.data.datasets[0].data.shift();
                        }
                        tpsChart.update();

                        // Consensus Chart
                        consensusChart.data.labels.push(timestamp);
                        consensusChart.data.datasets[0].data.push(
                            data.blockchain_metrics.consensus_time_avg * 1000
                        );
                        if (consensusChart.data.labels.length > 20) {
                            consensusChart.data.labels.shift();
                            consensusChart.data.datasets[0].data.shift();
                        }
                        consensusChart.update();

                        // Block Interval Chart
                        blockIntervalChart.data.labels.push(timestamp);
                        blockIntervalChart.data.datasets[0].data.push(
                            data.blockchain_metrics.block_time_avg
                        );
                        if (blockIntervalChart.data.labels.length > 20) {
                            blockIntervalChart.data.labels.shift();
                            blockIntervalChart.data.datasets[0].data.shift();
                        }
                        blockIntervalChart.update();
                    })
                    .catch(error => console.error('Error fetching metrics:', error));
            }

            // Update metrics every second
            setInterval(updateMetrics, 1000);
        </script>
    </body>
    </html>
    """

@app.get("/api/metrics")
async def get_metrics() -> Dict[str, Any]:
    """Get all aggregated metrics from BlockchainMetrics."""
    # Ensure metrics instance is set before trying to use it
    if metrics is None:
        raise HTTPException(status_code=500, detail="Metrics instance not initialized.")

    # Get all the metrics
    system_metrics = metrics.get_system_metrics()
    power_metrics = metrics.get_power_metrics()
    blockchain_metrics = metrics.get_blockchain_metrics()
    
    # Debug logging
    print(f"[DASHBOARD DEBUG] System metrics keys: {list(system_metrics.keys())}")
    for node_id, node_data in system_metrics.items():
        print(f"[DASHBOARD DEBUG] {node_id}: block_count={node_data.get('block_count', 'MISSING')}, pending_transactions={node_data.get('pending_transactions', 'MISSING')}")
    
    return {
        "consensus_protocol": "DPoS",
        "power_metrics": power_metrics,
        "blockchain_metrics": {
            **blockchain_metrics,
            # "total_blocks": 0 # Placeholder for now, to be fetched from storage
        },
        "system_metrics": system_metrics, # This now returns all nodes' metrics
        "all_validators_metrics": metrics.get_all_validators_metrics(),
        "current_elected_validator": metrics.get_current_elected_validator(),
        "blockchain_size": metrics.get_blockchain_size()
    }

@app.get("/api/chain_info")
async def get_chain_info() -> Dict[str, Any]:
    """Return the length of the local blockchain and the hash of the latest block."""
    if metrics is None:
        raise HTTPException(status_code=500, detail="Metrics instance not initialized.")
    
    chain_length = metrics.get_chain_length()
    latest_block_hash = metrics.get_latest_block_hash()

    return {
        "chain_length": chain_length,
        "latest_block_hash": latest_block_hash
    }

@app.get("/api/blocks")
async def get_blocks(start_index: int, end_index: int) -> List[Dict[str, Any]]:
    """Return a range of serialized blocks from the local blockchain."""
    if metrics is None:
        raise HTTPException(status_code=500, detail="Metrics instance not initialized.")

    blocks = metrics.get_blocks_from_storage(start_index, end_index)
    return [block.to_dict() for block in blocks]

@app.get("/api/consensus-protocol")
async def get_consensus_protocol() -> Dict[str, str]:
    """Get consensus protocol information."""
    return {"protocol": "DPoS"}

@app.get("/api/blockchain-metrics")
async def get_blockchain_metrics() -> Dict[str, Any]:
    """Get blockchain-specific metrics."""
    # Ensure metrics instance is set before trying to use it
    if metrics is None:
        raise HTTPException(status_code=500, detail="Metrics instance not initialized.")
    return metrics.get_blockchain_metrics()

@app.get("/api/system-metrics")
async def get_system_metrics() -> Dict[str, Any]:
    """Get system resource metrics."""
    return metrics.get_system_metrics() 

@app.get("/api/export/block-metrics.csv")
async def export_block_metrics_csv():
    if metrics is None:
        raise HTTPException(status_code=500, detail="Metrics instance not initialized.")
    # Pull data from storage via metrics.storage
    rows = metrics.storage.export_block_metrics()
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=["block_index", "created_timestamp", "block_interval", "consensus_time", "power_usage"])
    writer.writeheader()
    for r in rows:
        writer.writerow(r)
    output.seek(0)
    return StreamingResponse(output, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=block-metrics.csv"})

@app.get("/api/export/transaction-lifecycle.csv")
async def export_tx_lifecycle_csv():
    if metrics is None:
        raise HTTPException(status_code=500, detail="Metrics instance not initialized.")
    rows = metrics.storage.export_transaction_lifecycle()
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=["tx_hash", "received_timestamp", "included_timestamp", "block_index"])
    writer.writeheader()
    for r in rows:
        writer.writerow(r)
    output.seek(0)
    return StreamingResponse(output, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=transaction-lifecycle.csv"}) 