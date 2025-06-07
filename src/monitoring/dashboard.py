from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from typing import Dict, Any
import json
import os
from .metrics import BlockchainMetrics

app = FastAPI(title="Blockchain Dashboard")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize metrics
metrics = BlockchainMetrics()

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
                            <h5 class="card-title">Power Usage</h5>
                            <p class="card-text" id="power-usage">Loading...</p>
                        </div>
                    </div>
                </div>
            </div>

            <div class="row">
                <div class="col-md-6">
                    <div class="card metric-card">
                        <div class="card-body">
                            <h5 class="card-title">Transactions per Second</h5>
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
                            <h5 class="card-title">System Resources</h5>
                            <div class="chart-container">
                                <canvas id="resources-chart"></canvas>
                            </div>
                        </div>
                    </div>
                </div>
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
            // Initialize charts
            const tpsChart = new Chart(document.getElementById('tps-chart'), {
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

            const consensusChart = new Chart(document.getElementById('consensus-chart'), {
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

            const resourcesChart = new Chart(document.getElementById('resources-chart'), {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [{
                        label: 'CPU Usage (%)',
                        data: [],
                        borderColor: 'rgb(54, 162, 235)',
                        tension: 0.1
                    }, {
                        label: 'Memory Usage (%)',
                        data: [],
                        borderColor: 'rgb(255, 206, 86)',
                        tension: 0.1
                    }]
                }
            });

            const blockIntervalChart = new Chart(document.getElementById('block-interval-chart'), {
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

            // Update metrics every second
            function updateMetrics() {
                fetch('/api/metrics')
                    .then(response => response.json())
                    .then(data => {
                        // Update power usage
                        document.getElementById('power-usage').textContent = 
                            `Total: ${data.power_metrics.total_power.toFixed(2)}W`;

                        // Update charts
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

                        // Resources Chart
                        resourcesChart.data.labels.push(timestamp);
                        resourcesChart.data.datasets[0].data.push(data.system_metrics.cpu_percent);
                        resourcesChart.data.datasets[1].data.push(data.system_metrics.memory_percent);
                        if (resourcesChart.data.labels.length > 20) {
                            resourcesChart.data.labels.shift();
                            resourcesChart.data.datasets[0].data.shift();
                            resourcesChart.data.datasets[1].data.shift();
                        }
                        resourcesChart.update();

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
                    });
            }

            // Update metrics every second
            setInterval(updateMetrics, 1000);
        </script>
    </body>
    </html>
    """

@app.get("/api/metrics")
async def get_metrics() -> Dict[str, Any]:
    """Get all metrics."""
    return {
        "consensus_protocol": "DPoS",
        "power_metrics": metrics.get_power_metrics(),
        "blockchain_metrics": metrics.get_blockchain_metrics(),
        "system_metrics": metrics.get_system_metrics(),
        "blockchain_size": metrics.get_blockchain_size()
    }

@app.get("/api/consensus-protocol")
async def get_consensus_protocol() -> Dict[str, str]:
    """Get consensus protocol information."""
    return {"protocol": "DPoS"}

@app.get("/api/power-usage")
async def get_power_usage() -> Dict[str, float]:
    """Get power usage metrics."""
    return metrics.get_power_metrics()

@app.get("/api/blockchain-metrics")
async def get_blockchain_metrics() -> Dict[str, Any]:
    """Get blockchain-specific metrics."""
    return metrics.get_blockchain_metrics()

@app.get("/api/system-metrics")
async def get_system_metrics() -> Dict[str, Any]:
    """Get system resource metrics."""
    return metrics.get_system_metrics() 