import argparse
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
from src.utils.snapshot import load_snapshot, save_snapshot

def create_ssh_client(server_cfg):
    return SshClient(
        host_ip=server_cfg["ip"],
        host_port=server_cfg["port"],
        host_user=server_cfg["host_user"],
        host_password=server_cfg["password"],
    )

def collect_static_metrics(server_ip):
    server_cfg = next(s for s in config["servers"] if s["ip"] == server_ip)
    ssh_client = create_ssh_client(server_cfg)
    static_profile_info = load_snapshot("static_profile_info")
    if static_profile_info is None:
        collector = StaticMetricProfileCollector(ssh_client=ssh_client, max_workers=5)
        static_profile_info = collector.run()
        save_snapshot(static_profile_info, "static_profile_info")
    display_metrics(static_profile_info["static"], headers=["metric name", "metric value"])
    return static_profile_info

def collect_runtime_metrics(server_ip, pressure_test_mode=False):
    server_cfg = next(s for s in config["servers"] if s["ip"] == server_ip)
    ssh_client = create_ssh_client(server_cfg)
    data = load_snapshot("metrics_data")
    if data is None:
        metric_collector = MetricCollector(
            ssh_client=ssh_client,
            app=server_cfg["app"],
            pressure_test_mode=pressure_test_mode,
        )
        data = metric_collector.run()
        save_snapshot(data, "metrics_data")
    display_metrics(data, headers=["load type", "metric name", "metric value"])
    return data

def collect_micro_dependencies(server_ip, iterations=10):
    server_cfg = next(s for s in config["servers"] if s["ip"] == server_ip)
    ssh_client = create_ssh_client(server_cfg)
    micro_dep_data = load_snapshot("micro_dep_data")
    if micro_dep_data is None:
        micro_dep_collector = MicroDepCollector(
            ssh_client=ssh_client,
            iteration=iterations,
            target_process_name=server_cfg["target_process_name"],
            benchmark_cmd=config["benchmark_cmd"],
            mode=COLLECTMODE.DIRECT_MODE,
        )
        micro_dep_data = micro_dep_collector.run()
        save_snapshot(micro_dep_data, "micro_dep_data")
    logging.info(f"MicroDepCollector data: {micro_dep_data}")
    return micro_dep_data

def analyze_performance(server_ip):
    server_cfg = next(s for s in config["servers"] if s["ip"] == server_ip)
    data = load_snapshot("metrics_data")
    analyzer = PerformanceAnalyzer(data=data, app=server_cfg["app"])
    report = analyzer.run()
    save_snapshot(report, "analysis_report")
    return report

def optimize_params(server_ip, max_iterations=30):
    server_cfg = next(s for s in config["servers"] if s["ip"] == server_ip)
    report = load_snapshot("analysis_report")
    static_profile_info = load_snapshot("static_profile_info")
    ssh_client = create_ssh_client(server_cfg)
    optimizer = ParamOptimizer(
        service_name=server_cfg["app"],
        slo_goal=server_cfg["slo_goal"],
        analysis_report=report,
        static_profile=static_profile_info,
        ssh_client=ssh_client,
        max_iterations=max_iterations,
        need_restart_application=False,
        pressure_test_mode=False,
        tune_system_param=True,
        tune_app_param=True,
        need_recover_cluster=False,
        benchmark_timeout=600,
        param_save_path="best_params.json"
    )
    optimizer.run()
    return "Optimization complete"

def strategy_optimization(server_ip):
    server_cfg = next(s for s in config["servers"] if s["ip"] == server_ip)
    bottleneck = "cpu"  # 这里可以用实际分析结果替换
    ssh_client = create_ssh_client(server_cfg)
    strategy_optimizer = StrategyOptimizer(
        application=server_cfg["app"],
        bottle_neck=bottleneck,
        ssh_client=ssh_client,
        system_report=load_snapshot("analysis_report"),
        target_config_path="",
    )
    recommendations = strategy_optimizer.get_recommendations_json(bottleneck, top_k=1)
    save_snapshot(recommendations, "strategy_recommendations")
    logging.info(f"Strategy recommendations: {recommendations}")
    return recommendations

def main():
    parser = argparse.ArgumentParser(description="StartTune CLI for system tuning")
    parser.add_argument("action", choices=[
        "collect_static_metrics",
        "collect_runtime_metrics",
        "collect_micro_dependencies",
        "analyze_performance",
        "optimize_params",
        "strategy_optimization"
    ])
    parser.add_argument("--server", required=True, help="Target server IP")
    parser.add_argument("--iterations", type=int, default=10, help="Iterations for micro dep or param optimization")
    parser.add_argument("--pressure", action="store_true", help="Enable pressure test for runtime metrics")
    args = parser.parse_args()

    if args.action == "collect_static_metrics":
        collect_static_metrics(args.server)
    elif args.action == "collect_runtime_metrics":
        collect_runtime_metrics(args.server, pressure_test_mode=args.pressure)
    elif args.action == "collect_micro_dependencies":
        collect_micro_dependencies(args.server, iterations=args.iterations)
    elif args.action == "analyze_performance":
        analyze_performance(args.server)
    elif args.action == "optimize_params":
        optimize_params(args.server, max_iterations=args.iterations)
    elif args.action == "strategy_optimization":
        strategy_optimization(args.server)
    else:
        print("Unknown action")

if __name__ == "__main__":
    main()
