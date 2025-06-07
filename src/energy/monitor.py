import psutil
import time
from typing import Dict, Any
import os

class EnergyMonitor:
    def __init__(self):
        self.cpu_threshold = 80  # Maximum CPU usage percentage
        self.memory_threshold = 80  # Maximum memory usage percentage
        self.temperature_threshold = 80  # Maximum temperature in Celsius
        
    def get_system_metrics(self) -> Dict[str, float]:
        """Get current system metrics."""
        return {
            'cpu_percent': psutil.cpu_percent(interval=1),
            'memory_percent': psutil.virtual_memory().percent,
            'temperature': self._get_temperature(),
            'power_usage': self._estimate_power_usage()
        }
        
    def _get_temperature(self) -> float:
        """Get CPU temperature for Raspberry Pi."""
        try:
            temp = os.popen('vcgencmd measure_temp').readline()
            return float(temp.replace('temp=', '').replace("'C\n", ''))
        except:
            return 0.0
            
    def _estimate_power_usage(self) -> float:
        """Estimate power usage based on CPU and memory usage."""
        cpu_usage = psutil.cpu_percent()
        memory_usage = psutil.virtual_memory().percent
        
        # Simple power estimation model
        base_power = 0.5  # Base power consumption in watts
        cpu_power = (cpu_usage / 100) * 2.0  # CPU power consumption
        memory_power = (memory_usage / 100) * 0.5  # Memory power consumption
        
        return base_power + cpu_power + memory_power
        
    def should_throttle(self) -> bool:
        """Check if system should be throttled based on metrics."""
        metrics = self.get_system_metrics()
        
        return (
            metrics['cpu_percent'] > self.cpu_threshold or
            metrics['memory_percent'] > self.memory_threshold or
            metrics['temperature'] > self.temperature_threshold
        )
        
    def get_optimization_suggestions(self) -> Dict[str, Any]:
        """Get suggestions for energy optimization."""
        metrics = self.get_system_metrics()
        suggestions = {
            'throttle_cpu': metrics['cpu_percent'] > self.cpu_threshold,
            'reduce_memory': metrics['memory_percent'] > self.memory_threshold,
            'cool_down': metrics['temperature'] > self.temperature_threshold,
            'power_saving_mode': metrics['power_usage'] > 2.0
        }
        
        return {
            'metrics': metrics,
            'suggestions': suggestions,
            'timestamp': time.time()
        } 