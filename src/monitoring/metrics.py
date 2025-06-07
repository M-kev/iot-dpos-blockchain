class BlockchainMetrics:
    def __init__(self):
        self.metrics = {}

    def record_block_time(self, value):
        self.metrics['block_time'] = value

    def record_consensus_time(self, value):
        self.metrics['consensus_time'] = value

    def record_transactions(self, value):
        self.metrics['transactions'] = value

    def record_propagation_delay(self, value):
        self.metrics['propagation_delay'] = value

    def get_power_metrics(self):
        return {"total_power": 0.0}

    def get_blockchain_metrics(self):
        return {
            "tps": 0,
            "consensus_time_avg": 0,
            "block_time_avg": 0
        }

    def get_system_metrics(self):
        return {
            "cpu_percent": 0,
            "memory_percent": 0
        }

    def get_blockchain_size(self):
        return 0 