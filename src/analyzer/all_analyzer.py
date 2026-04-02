import sys
import os
# Get the absolute path of the project root directory
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# Add project root to sys.path
sys.path.append(project_root)
from src.analyzer.cpu_analyzer import CpuAnalyzer
from src.analyzer.disk_analyzer import DiskAnalyzer
from src.analyzer.memory_analyzer import MemoryAnalyzer
from src.analyzer.network_analyzer import NetworkAnalyzer
from src.analyzer.base_analyzer import BaseAnalyzer
from typing import Tuple

class Analyzer(BaseAnalyzer):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.cpu_analyzer = CpuAnalyzer(data=self.data.get("Cpu", {}))
        self.disk_analyzer = DiskAnalyzer(data=self.data.get("Disk", {}))
        self.memory_analyzer = MemoryAnalyzer(data=self.data.get("Memory", {}))
        self.network_analyzer = NetworkAnalyzer(data=self.data.get("Network", {}))

    def analyze(
        self,
        report: str
    ) -> str:
        bottle_neck_prompt = f"""
        # CONTEXT #
        The current Linux system performance analysis report is as follows, and the data mentioned in the report is accurate and trustworthy:
        {report}

        # OBJECTIVE #
        Based on the system performance analysis report, determine whether the current system has a performance bottleneck; if a bottleneck exists, identify which aspect of the system it mainly exists in.
        You should consider multiple pieces of information and metrics comprehensively and avoid drawing conclusions based on a single data point. > Your final conclusion should be supported by multiple pieces of evidence.
        Requirements:
        1. You must choose one option from [CPU, NETWORK, DISK, MEMORY, NONE] as your answer.
        2. Do not include extra text, your answer must strictly match one of the above options.
        3. If you believe there is no performance bottleneck, choose NONE.

        # STYLE #
        You are a professional system operations expert, only answer with one of the above five options.

        # TONE #
        You should maintain a serious, careful, and rigorous attitude.
        # AUDIENCE #
        Your answer will serve as an important reference for other system operations experts, please think carefully before providing your answer.

        # RESPONSE FORMAT #
        Please respond with only one of the five options above, without extra text.
        """
        result = self.ask_llm(bottle_neck_prompt)
        bottlenecks = {
            "cpu": "CPU",
            "disk": "DISK",
            "network": "NETWORK",
            "memory": "MEMORY",
            "none": "NONE"
        }

        # Convert to lowercase and find the bottleneck
        for key, value in bottlenecks.items():
            if key in result.lower():
                return value

        # If no clear bottleneck is found, return UNKNOWN BOTTLENECKS
        return "UNKNOWN BOTTLENECKS"

    def generate_report(self) -> Tuple[str, str]:
        os_performance_report = ""
        os_performance_report += self.cpu_analyzer.run()
        os_performance_report += self.disk_analyzer.run()
        os_performance_report += self.memory_analyzer.run()
        os_performance_report += self.network_analyzer.run()
        app_performance_report = ""

        # app_performance_report += self.mysql_analyzer.run()
        return os_performance_report, app_performance_report

    def generate_cpu_report(self) -> str:
        cpu_report = ""
        cpu_report += self.cpu_analyzer.run()
        return cpu_report

    def generate_disk_report(self) -> str:
        disk_report = ""
        disk_report += self.disk_analyzer.run()
        return disk_report

    def generate_memory_report(self) -> str:
        memory_report = ""
        memory_report += self.memory_analyzer.run()
        return memory_report

    def generate_network_report(self) -> str:
        network_report = ""
        network_report += self.network_analyzer.run()
        return network_report

    def run(self) -> Tuple[str, str]:
        os_performance_report, app_performance_report = self.generate_report()
        bottleneck = self.analyze(os_performance_report)
        return os_performance_report + app_performance_report, bottleneck

    def summarize_bottlenecks(
        self,
        report: str
    ) -> str:
        bottle_neck_prompt = f"""
        # CONTEXT #
        The current Linux system performance analysis report is as follows, and the data mentioned in the report is accurate and trustworthy:
        {report}

        # OBJECTIVE #
        Based on the system performance analysis report, provide a quantitative score for potential performance bottlenecks. You need to provide a score (0~1) for each of the following aspects to indicate the pressure or bottleneck level in the system:
        [CPU, NETWORK, DISK, MEMORY, NONE]

        Scoring requirements:
        1. 0 indicates no bottleneck, 1 indicates a severe bottleneck.
        2. You must consider multiple metrics and multiple pieces of information comprehensively, and avoid drawing conclusions based on a single data point.
        3. The score for NONE indicates that the system has no obvious bottleneck. If bottlenecks exist, NONE should be 0.

        # STYLE #
        You are a professional system operations expert and should only return the scoring results.

        # TONE #
        Please maintain a serious, careful, and rigorous attitude.

        # AUDIENCE #
        Your scoring will serve as an important reference for other system operations experts, please think carefully before providing your answer.

        # RESPONSE FORMAT #
        Please return the results in JSON format, example:
        {
        "CPU": 0.7,
        "NETWORK": 0.2,
        "DISK": 0.5,
        "MEMORY": 0.3,
        "NONE": 0
        }
        Do not include extra text, and ensure the JSON can be parsed directly.
        """
        result = self.ask_llm(bottle_neck_prompt)
        bottlenecks = {
            "cpu": "CPU",
            "disk": "DISK",
            "network": "NETWORK",
            "memory": "MEMORY",
            "none": "NONE"
        }

        # Convert to lowercase and find the bottleneck
        for key, value in bottlenecks.items():
            if key in result.lower():
                return value

        # If no clear bottleneck is found, return UNKNOWN BOTTLENECKS
        return "UNKNOWN BOTTLENECKS"