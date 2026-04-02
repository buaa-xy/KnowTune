import sys
import os
# Get the absolute path of the project root directory
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# Add the project root directory to sys.path
sys.path.append(project_root)
from src.collector.cpu_collector import CpuCollector, get_cpu_cmd
from src.collector.disk_collector import DiskCollector, get_disk_cmd
from src.collector.memory_collector import MemoryCollector, get_memory_cmd
from src.collector.network_collector import NetworkCollector, get_network_cmd
from src.collector.base_collector import CollectorArgs

class MetricCollector:
    def __init__(self, host_ip: str, host_port: int, host_user: str, host_password: str, app: str = None):
        self.args = CollectorArgs(
            host_ip=host_ip,
            host_port=host_port,
            host_user=host_user,
            host_password=host_password,
        )
        self.app = app  
        self.cpu_collector = CpuCollector(
            cmd = get_cpu_cmd(),
            host_ip=self.args.host_ip,
            host_port=self.args.host_port,
            host_user=self.args.host_user,
            host_password=self.args.host_password
        )
        self.disk_collector = DiskCollector(
            cmd = get_disk_cmd(),
            host_ip=self.args.host_ip,
            host_port=self.args.host_port,
            host_user=self.args.host_user,
            host_password=self.args.host_password
        )
        self.memory_collector = MemoryCollector(
            cmd = get_memory_cmd(),
            host_ip=self.args.host_ip,
            host_port=self.args.host_port,
            host_user=self.args.host_user,
            host_password=self.args.host_password
        )
        self.network_collector = NetworkCollector(
            cmd = get_network_cmd(),
            host_ip=self.args.host_ip,
            host_port=self.args.host_port,
            host_user=self.args.host_user,
            host_password=self.args.host_password
        )

    def run_cpu_collector(self) -> dict:
        """
        Run the CPU collector, collect and return the aggregated results.
        """
        # Call the run method of each sub-collector
        cpu_data = self.cpu_collector.run()
        # Merge all collected data
        CPU_data = {
            "Cpu": cpu_data,
        }
        return CPU_data

    def run_disk_collector(self) -> dict:
        """
        Run the disk collector, collect and return the aggregated results.
        """
        # Call the run method of each sub-collector
        disk_data = self.disk_collector.run()
        # Merge all collected data
        DISK_data = {
            "Disk": disk_data,
        }
        return DISK_data

    def run_memory_collector(self) -> dict:
        """
        Run the memory collector, collect and return the aggregated results.
        """
        # Call the run method of each sub-collector
        memory_data = self.memory_collector.run()
        # Merge all collected data
        MEMORY_data = {
            "Memory": memory_data,
        }
        return MEMORY_data

    def run_network_collector(self) -> dict:
        """
        Run the network collector, collect and return the aggregated results.
        """
        # Call the run method of each sub-collector
        network_data = self.network_collector.run()
        # Merge all collected data
        NETWORK_data = {
            "Network": network_data,
        }
        return NETWORK_data