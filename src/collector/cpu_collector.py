from .base_collector import BaseCollector
from typing import Dict, Any, List
import logging
import json
from enum import Enum
import re

class CpuMetric(Enum):
    ONE_MINUTE_AVG_LOAD = "1min"
    FIVE_MINUTE_AVG_LOAD  = "5min"
    TEN_MINUTE_AVG_LOAD  = "10min"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

perf = "perf stat -e 'syscalls:*' -a sleep 1 2>&1 | grep syscalls| awk '{sum += $1} END {print sum}'"

def get_cpu_cmd()-> List[str]:
    return list(CPU_PARSE_FUNCTIONS.keys())
    
def nproc_parse(
    cmd: str,
    stdout: Any,
) -> Dict:
    if cmd != "nproc":
        logging.error("Command is not 'nproc'.")
        raise ValueError("Command must be 'nproc'")
    
    if not isinstance(stdout, str):
        logging.error("Input stdout is not a string.")
        raise TypeError("Expected stdout to be a string")

    try:
        logical_cpu_cores = int(stdout.split("\n")[0])
    except (IndexError, ValueError) as e:
        logging.error(f"Failed to parse CPU count from stdout: {e}")
        raise ValueError("Failed to parse CPU count from stdout") from e

    res = {"cpu_cores": logical_cpu_cores}
    return res

def loadavg_parse(
    cmd: str,
    stdout: Any,
) -> Dict:
    if cmd != "cat /proc/loadavg":
        logging.error("Command is not 'cat /proc/loadavg'.")
        raise ValueError("Command must be 'cat /proc/loadavg'")
    
    if not isinstance(stdout, str):
        logging.error("Input stdout is not a string.")
        raise TypeError("Expected stdout to be a string")

    try:
        out = stdout.split("\n")
        data = out[0].split()
        if len(data) < 3:
            raise ValueError("Not enough data to parse load averages.")
        
        load_avgs = {"1min_avg_load": float(data[0]),
                     "5min_avg_load": float(data[1]),
                     "10min_avg_load": float(data[2])}
    except (IndexError, ValueError) as e:
        logging.error(f"Failed to parse system load averages from stdout: {e}")
        raise ValueError("Failed to parse system load averages from stdout") from e

    return load_avgs

def perf_syscall_parse(
    cmd: str,
    stdout: Any,
) -> Dict:
    if cmd != perf:
        logging.error("Command is not 'perf'.")
        raise ValueError("Command must be 'perf'")

    if not isinstance(stdout, str):
        logging.error("Input stdout is not a string.")
        raise TypeError("Expected stdout to be a string")

    try:
        sys_call_rate = float(stdout.split("\n")[0])
    except (IndexError, ValueError) as e:
        logging.error(f"Failed to parse system call rate from stdout: {e}")
        raise ValueError("Failed to parse system call rate from stdout") from e

    res = {"system_calls_per_unit_time": sys_call_rate}
    return res


def mpstat_parse(
    cmd: str,
    stdout: Any,
) -> Dict:
    if cmd != "mpstat -P ALL 1 1":
        logging.error("Command is not 'mpstat'.")
        raise ValueError("Command must be 'mpstat'")

    if not isinstance(stdout, str):
        logging.error("Input stdout is not a string.")
        raise TypeError("Expected stdout to be a string")

    lines = stdout.strip().splitlines()

    # Locate the header line
    header_idx = None
    for i, line in enumerate(lines):
        if "CPU" in line and "%usr" in line:
            header_idx = i
            break
    if header_idx is None:
        logging.error("Cannot find header line in mpstat output.")
        raise ValueError("Unexpected mpstat output format: missing header")

    header_cols = lines[header_idx].split()
    try:
        cpu_col = header_cols.index("CPU")
    except ValueError:
        logging.error("Header line malformed: no 'CPU' column")
        raise ValueError("Malformed header in mpstat output")

    metric_names = header_cols[cpu_col+1:]

    english_keys = [
        "user_cpu_usage",
        "nice_user_cpu_usage",
        "kernel_cpu_usage",
        "iowait_cpu_usage",
        "hard_interrupt_cpu_usage",
        "soft_interrupt_cpu_usage",
        "virtualization_other_cpu_usage",
        "guest_cpu_usage",
        "guest_nice_cpu_usage",
        "idle_cpu_usage",
    ]
    if len(english_keys) != len(metric_names):
        raise ValueError("Number of English keys does not match mpstat columns")

    # Find and parse 'all' line
    for line in lines[header_idx + 1:]:
        if "Average:" not in line:
            continue
        parts = line.split()
        if "Average:" not in parts or len(parts) < parts.index("Average:") + 2:
            continue
        cpu_id = parts[parts.index("Average:") + 1]
        if cpu_id != "all":
            continue

        values = parts[parts.index("Average:") + 2 : parts.index("Average:") + 2 + len(english_keys)]
        if len(values) < len(english_keys):
            logging.error(f"Columns count mismatch for all: {values}")
            raise ValueError("mpstat output columns mismatch")

        result: Dict[str, float] = {}
        for key, val in zip(english_keys, values):
            try:
                result[key] = float(val)
            except ValueError:
                logging.error(f"Cannot convert '{val}' to float for all")
                raise ValueError(f"Invalid number '{val}' in mpstat output")
        return result

    # 'all' line not found
    logging.error("No 'Average: all' line found in mpstat output.")
    raise ValueError("Unexpected mpstat output format: no 'Average: all' line")


def process_parse(cmd, stdout):
    if cmd != "ps aux|wc -l":
        logging.error("Command is not 'ps aux|wc -l'.")
        raise ValueError("Command is not 'ps aux|wc -l'.")

    if not isinstance(stdout, str):
        logging.error("Input stdout is not a string.")
        raise TypeError("Expected stdout to be a string")

    try:
        total_process = float(stdout.split("\n")[0])
    except (ValueError, IndexError) as e:
        logging.error(f"Failed to parse total process count from stdout: {e}")
        raise ValueError("Failed to parse total process count from stdout") from e

    res = {"total_processes": total_process}
    return res

def vmstat_parse(
    cmd: str,
    stdout: Any,
) -> Dict:
    if cmd != "vmstat 1 2":
        logging.error("Command is not 'vmstat'.")
        raise ValueError("Command is not 'vmstat'.")

    if not isinstance(stdout, str):
        logging.error("Input stdout is not a string.")
        raise TypeError("Expected stdout to be a string")

    try:
        out = stdout.split("\n")
        out.pop() 
        data = out[-1].split()

        run_queue_len = int(data[0])  
        blocked_num = int(data[1])  
        context_switch = int(data[11])  

        res = {
            "run_queue_length": run_queue_len,
            "blocked_processes": blocked_num,
            "context_switches_per_second": context_switch
        }
    except IndexError as e:
        logging.error(f"Failed to parse vmstat memory attributes: {e}")
        raise ValueError("Failed to parse vmstat memory attributes from stdout") from e
    except ValueError as e:
        logging.error(f"Failed to convert vmstat values to expected types: {e}")
        raise ValueError("Failed to convert vmstat values to expected types") from e

    return res

def pid_parse(
    cmd: str,
    stdout: Any,
) -> Dict:
    if cmd != "pidstat -d | head -6":
        logging.error("Command is not 'pidstat'.")
        raise ValueError("Command is not 'pidstat'.")
    return {"process_info": stdout}

CPU_PARSE_FUNCTIONS = {
    "nproc": nproc_parse,
    "cat /proc/loadavg": loadavg_parse,
    perf: perf_syscall_parse,
    #"mpstat -P ALL -o JSON 1 1": mpstat_parse,
    "mpstat -P ALL 1 1": mpstat_parse,
    "ps aux|wc -l": process_parse,
    "vmstat 1 2": vmstat_parse,
    "pidstat -d | head -6": pid_parse,
}

class CpuCollector(BaseCollector):
    def __init__(self, cmd: List[str], **kwargs):
        # Add cmd to kwargs
        kwargs['cmds'] = cmd
        super().__init__(**kwargs)
    
    def parse_cmd_stdout(
        self,
        cpu_info_stdout: Dict[str, Any],
    ) -> Dict:
        parse_result = {}
        for k, v in cpu_info_stdout.items():
            # Use dict to get corresponding parse function, if cmd not in dict use default parse
            parse_function = CPU_PARSE_FUNCTIONS.get(k, self.default_parse)
            cmd_parse_result = parse_function(k, v)
            parse_result = {**parse_result, **cmd_parse_result}
        return parse_result

    def normalize_percentage(
        self,
        value: Any, 
        total: float,
    ) -> float:
        return value / total if total != 0 else 0

    def is_heavy_load(
        self,
        usage: float,
    ) -> bool:
        return usage > 70

    def data_process(
        self, 
        cpu_parse_result: Dict,
    ) -> Dict:
        cpu_process_result = {}
        
        # Calculate average load
        for metric in [CpuMetric.ONE_MINUTE_AVG_LOAD, CpuMetric.FIVE_MINUTE_AVG_LOAD, CpuMetric.TEN_MINUTE_AVG_LOAD]:
            cpu_process_result[metric.value] = self.normalize_percentage(
                cpu_parse_result[f"{metric.value}_avg_load"], 
                cpu_parse_result["cpu_cores"]
            )
        
        # Calculate CPU utilization
        cpu_utilizations = [
            "user_cpu_usage",
            "nice_user_cpu_usage",
            "kernel_cpu_usage"
        ]
        for utilization in cpu_utilizations:
            cpu_process_result[utilization] = self.normalize_percentage(
                cpu_parse_result[utilization], 100
            )
        
        # Other percentage calculations
        for key in [
            "hard_interrupt_cpu_usage",
            "soft_interrupt_cpu_usage",
            "virtualization_other_cpu_usage",
            "guest_cpu_usage",
            "guest_nice_cpu_usage"
        ]:
            cpu_process_result[key] = self.normalize_percentage(
                cpu_parse_result[key], 100
            )
        
        # CPU utilization and context switch rate
        cpu_process_result["cpu_utilization"] = 1 - self.normalize_percentage(
            cpu_parse_result["idle_cpu_usage"], 100
        )
        cpu_process_result["context_switches_per_second"] = cpu_parse_result.get(
            "context_switches_per_second", 0
        )
        
        # Blocked process ratio
        cpu_process_result["blocked_process_ratio"] = self.normalize_percentage(
            cpu_parse_result.get("blocked_processes", 0), cpu_parse_result.get("total_processes", 1)
        )
        
        # Ensure kernel CPU usage is not zero
        cpu_process_result["kernel_cpu_usage"] = max(
            0.01, cpu_process_result["kernel_cpu_usage"]
        )
        
        # Determine compute-bound or IO-bound
        user_mode_ratio = cpu_process_result["user_cpu_usage"] / cpu_process_result["kernel_cpu_usage"]
        is_heavy_io = self.is_heavy_load(cpu_process_result["user_cpu_usage"]) or self.is_heavy_load(cpu_process_result["kernel_cpu_usage"])
        
        if user_mode_ratio > 2:
            cpu_process_result["compute_bound"] = 1 if is_heavy_io else 0
        else:
            cpu_process_result["compute_bound"] = 0
        
        if user_mode_ratio < 2:
            cpu_process_result["io_bound"] = 1 if is_heavy_io else 0
        else:
            cpu_process_result["io_bound"] = 0
        
        # Copy other info
        cpu_process_result["process_info"] = cpu_parse_result.get("process_info", [])
        cpu_process_result["system_calls_per_unit_time"] = cpu_parse_result.get("system_calls_per_unit_time", 0)
        cpu_process_result["cpu_cores"] = cpu_parse_result.get("cpu_cores", 0)
        
        return cpu_process_result