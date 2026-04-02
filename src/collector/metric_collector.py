import sys
import os
# 获取项目根目录的绝对路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# 将项目根目录添加到 sys.path
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
        self.app = app  # 新增app属性
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
        运行所有数据收集器，收集并返回综合结果。
        """
        # 调用每个子收集器的 run 方法
        cpu_data = self.cpu_collector.run()
        # 合并所有收集到的数据
        CPU_data = {
            "Cpu": cpu_data,
        }
        return CPU_data

    def run_disk_collector(self) -> dict:
        """
        运行所有数据收集器，收集并返回综合结果。
        """
        # 调用每个子收集器的 run 方法
        disk_data = self.disk_collector.run()
        # 合并所有收集到的数据
        DISK_data = {
            "Disk": disk_data,
        }
        return DISK_data

    def run_memory_collector(self) -> dict:
        """
        运行所有数据收集器，收集并返回综合结果。
        """
        # 调用每个子收集器的 run 方法
        memory_data = self.memory_collector.run()
        # 合并所有收集到的数据
        MEMORY_data = {
            "Memory": memory_data,
        }
        return MEMORY_data

    def run_network_collector(self) -> dict:
        """
        运行所有数据收集器，收集并返回综合结果。
        """
        # 调用每个子收集器的 run 方法
        network_data = self.network_collector.run()
        # 合并所有收集到的数据
        NETWORK_data = {
            "Network": network_data,
        }
        return NETWORK_data



if __name__ == "__main__":
    collector = MetricCollector(
        host_ip="121.41.164.113",
        host_port=22,
        host_user="root",
        host_password="Euler123456"
    )
    print(collector.run_cpu_collector())
    print(collector.run_disk_collector())
    print(collector.run_memory_collector())
    print(collector.run_network_collector())