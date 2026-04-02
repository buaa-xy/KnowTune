import logging

from src.performance_collector.micro_dep_collector import MicroDepCollector, COLLECTMODE
from src.config import config
from src.performance_analyzer.performance_analyzer import PerformanceAnalyzer
from src.performance_collector.metric_collector import MetricCollector
from src.performance_collector.static_metric_profile_collector import StaticMetricProfileCollector
from src.performance_optimizer.param_optimizer import ParamOptimizer
from src.performance_optimizer.strategy_optimizer import StrategyOptimizer
from src.performance_test.pressure_test import PressureTest
from src.utils.collector.collector_trigger import TriggerEventListener
from src.utils.common import display_metrics
from src.utils.shell_execute import SshClient
import json
import os
from datetime import datetime

def setup_logging():
    """Configure logging format and level"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def create_ssh_client(server_cfg):
    """Create an SSH client based on server configuration"""
    return SshClient(
        host_ip=server_cfg["ip"],
        host_port=server_cfg["port"],
        host_user=server_cfg["host_user"],
        host_password=server_cfg["password"],
        max_retries=server_cfg["max_retries"],
        delay=server_cfg["delay"],
    )


def collect_static_metrics(ssh_client):
    """Collect static system and environment metrics"""
    static_collector = StaticMetricProfileCollector(ssh_client=ssh_client, max_workers=5)
    static_profile_info = static_collector.run()
    display_metrics(static_profile_info["static"], headers=["Metric Name", "Value"])
    return static_profile_info


def run_pressure_test_if_needed(server_cfg, ssh_client, enabled):
    """Run pressure test if enabled"""
    if not enabled:
        return
    logging.info("[Main] start pressure test ...")
    pressure_test = PressureTest(server_cfg["app"], ssh_client)
    listener = TriggerEventListener().configure(
        host=server_cfg["ip"],
        port=server_cfg["port"],
        user=server_cfg["host_user"],
        password=server_cfg["password"],
    )
    listener.run()
    pressure_test.start()


def collect_runtime_metrics(ssh_client, server_cfg, pressure_test_mode):
    """Collect runtime performance metrics"""
    metric_collector = MetricCollector(
        ssh_client=ssh_client,
        app=server_cfg["app"],
        pressure_test_mode=pressure_test_mode,
    )
    data = metric_collector.run()
    display_metrics(data, headers=["Workload Type", "Metric Name", "Value"])
    return data


def collect_micro_dependencies_if_needed(ssh_client, data, server_cfg, need_micro_dep):
    """Collect micro-dependency information if required"""
    if not need_micro_dep:
        return data
    micro_dep_collector = MicroDepCollector(
        ssh_client=ssh_client,
        iteration=10,
        target_process_name=server_cfg["target_process_name"],
        benchmark_cmd=config["benchmark_cmd"],
        mode=COLLECTMODE.DIRECT_MODE,
    )
    micro_dep_data = micro_dep_collector.run()
    logging.info(f"MicroDepCollector data: {micro_dep_data}")
    data["micro_dep"] = micro_dep_data
    return data


def analyze_performance(data, app):
    """Analyze performance bottlenecks"""
    logging.info("[Main] analyzing performance ...")
    analyzer = PerformanceAnalyzer(data=data, app=app)
    return analyzer.run()


def save_profile_data(static_data, metrics_data, report, output_dir="/home"):
    """
    Merge static and runtime metrics and save to the specified directory with timestamp
    """
    os.makedirs(output_dir, exist_ok=True)

    merged = {
        "timestamp": datetime.now().isoformat(),
        "static": static_data,
        "metrics_data": metrics_data,
        "report": report
    }

    file_path = os.path.join(output_dir, f"profile_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)

    print(f"[+] Performance data saved to: {file_path}")
    return file_path

def main():
    setup_logging()
    server_cfg = config["servers"][0]
    feature_cfg = config["feature"][0]

    ssh_client = create_ssh_client(server_cfg)

    static_profile_info = collect_static_metrics(ssh_client)
    run_pressure_test_if_needed(server_cfg, ssh_client, feature_cfg["pressure_test_mode"])

    metrics_data = collect_runtime_metrics(ssh_client, server_cfg, feature_cfg["pressure_test_mode"])
    metrics_data = collect_micro_dependencies_if_needed(ssh_client, metrics_data, server_cfg,
                                                        feature_cfg["microDep_collector"])

    report, bottleneck = analyze_performance(metrics_data, server_cfg["app"])
    save_profile_data(static_profile_info, metrics_data, report, output_dir="/home")


if __name__ == "__main__":
    main()
