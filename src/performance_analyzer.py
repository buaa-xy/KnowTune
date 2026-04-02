import logging
import json
import os
from datetime import datetime

from src.collector.micro_dep_collector import MicroDepCollector, COLLECTMODE
from src.analyzer.performance_analyzer import PerformanceAnalyzer
from src.collector.metric_collector import MetricCollector
from src.collector.static_collector import collect_system_profile
from src.utils.shell_execute import SshClient


class PerformanceAnalyzer:
    """
    A class-based implementation of the performance profiling workflow.
    It performs:
        - static profiling
        - runtime metrics collection
        - optional micro-dependency collection
        - performance analysis
        - profile export
    """

    def __init__(self, config):
        """
        Initialize the profiler with configuration.

        Args:
            config (dict): full configuration dictionary
        """
        self.config = config
        self.server_cfg = config["servers"][0]
        self.feature_cfg = config["feature"][0]

        self.ssh_client = None

    # -----------------------------------------------------------
    # Logging setup
    # -----------------------------------------------------------
    @staticmethod
    def setup_logging():
        """
        Configure logging format, log level, and output style.
        """
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    # -----------------------------------------------------------
    # SSH client
    # -----------------------------------------------------------
    def create_ssh_client(self):
        """
        Create SSH client from configuration.
        """
        self.ssh_client = SshClient(
            host_ip=self.server_cfg["ip"],
            host_port=self.server_cfg["port"],
            host_user=self.server_cfg["host_user"],
            host_password=self.server_cfg["password"],
            max_retries=self.server_cfg["max_retries"],
            delay=self.server_cfg["delay"],
        )

    # -----------------------------------------------------------
    # Static metrics
    # -----------------------------------------------------------
    def collect_static_metrics(self):
        """
        Collect static system metrics (CPU, memory, hardware, OS).
        """
        static_collector = collect_system_profile(
            ssh_client=self.ssh_client,
            max_workers=5
        )
        return static_collector.run()

    # -----------------------------------------------------------
    # Runtime metrics
    # -----------------------------------------------------------
    def collect_runtime_metrics(self):
        """
        Collect runtime performance metrics using MetricCollector.
        """
        metric_collector = MetricCollector(
            ssh_client=self.ssh_client,
            app=self.server_cfg["app"],
            pressure_test_mode=self.feature_cfg["pressure_test_mode"],
        )
        return metric_collector.run()

    # -----------------------------------------------------------
    # Micro-dependency (optional)
    # -----------------------------------------------------------
    def collect_micro_dependencies(self, data):
        """
        Optionally collect micro-dependency metrics if enabled.
        """
        if not self.feature_cfg["microDep_collector"]:
            return data

        micro_dep_collector = MicroDepCollector(
            ssh_client=self.ssh_client,
            iteration=10,
            target_process_name=self.server_cfg["target_process_name"],
            benchmark_cmd=self.config["benchmark_cmd"],
            mode=COLLECTMODE.DIRECT_MODE,
        )

        micro_dep_data = micro_dep_collector.run()
        logging.info(f"MicroDepCollector data: {micro_dep_data}")

        data["micro_dep"] = micro_dep_data
        return data

    # -----------------------------------------------------------
    # Performance analysis
    # -----------------------------------------------------------
    @staticmethod
    def analyze_performance(data, app):
        """
        Analyze performance metrics and identify bottlenecks.
        """
        logging.info("[Main] analyzing performance ...")
        analyzer = PerformanceAnalyzer(data=data, app=app)
        return analyzer.run()

    # -----------------------------------------------------------
    # Save JSON report
    # -----------------------------------------------------------
    @staticmethod
    def save_profile_data(static_data, metrics_data, report, output_dir="/home"):
        """
        Save merged profile data into a timestamped JSON file.
        """
        os.makedirs(output_dir, exist_ok=True)

        merged = {
            "timestamp": datetime.now().isoformat(),
            "static": static_data,
            "metrics_data": metrics_data,
            "report": report,
        }

        file_path = os.path.join(
            output_dir,
            f"profile_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(merged, f, ensure_ascii=False, indent=2)

        print(f"[+] Performance data saved to: {file_path}")
        return file_path

    # -----------------------------------------------------------
    # Full run
    # -----------------------------------------------------------
    def run(self):
        """
        Execute full profiling pipeline.
        """
        self.setup_logging()
        self.create_ssh_client()

        # 1. Static profiling
        static_data = self.collect_static_metrics()

        # 2. Runtime profiling
        metrics_data = self.collect_runtime_metrics()

        # 3. Micro-dependencies (optional)
        metrics_data = self.collect_micro_dependencies(metrics_data)

        # 4. Analyze performance
        report, bottleneck = self.analyze_performance(
            metrics_data, self.server_cfg["app"]
        )

        # 5. Save results
        self.save_profile_data(static_data, metrics_data, report, output_dir="/home")

        return report, bottleneck


# --------------------------------------------------------------------
# Instantiate and run
# --------------------------------------------------------------------
if __name__ == "__main__":
    config = {
        "servers": [
            {
                "ip": "127.0.0.1",
                "port": 22,
                "host_user": "",
                "password": "",
                "max_retries": 3,
                "delay": 2,
                "app": "mysql",
                "target_process_name": "mysqld"
            }
        ],
        "feature": [
            {
                "pressure_test_mode": "sysbench",
                "microDep_collector": False
            }
        ],
        "benchmark_cmd": "sysbench oltp_read_write run"
    }

    profiler = PerformanceAnalyzer(config)
    profiler.run()