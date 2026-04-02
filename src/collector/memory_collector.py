from .base_collector import BaseCollector
from typing import Dict, Any, List
import logging
from enum import Enum

class MemoryMetric(Enum):
    TODO = "XX"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

omm_kill_cmd = "(oom_kill1=$(cat /proc/vmstat | grep oom_kill | awk '{print$2}'); sleep 5; oom_kill2=$(cat /proc/vmstat | grep oom_kill | awk '{print$2}')) && echo $((oom_kill2 - oom_kill1))"

def get_memory_cmd() -> List[str]:
    return list(MEMORY_PARSE_FUNCTIONS.keys())

def free_parse(
    cmd: str, 
    stdout: Any,
) -> Dict:
    if cmd != "free":
        logging.error("Command is not 'free'.")
        raise ValueError("Command is not 'free'.")

    if not isinstance(stdout, str):
        logging.error("Input stdout is not a string.")
        raise TypeError("Expected stdout to be a string")

    try:
        out = stdout.split("\n")
        out.pop()
        data = out[-1].split()
        total_swap = float(data[1])  
        free_swap = float(data[3])  

        res = {"total_swap_space": total_swap, "available_swap_space": free_swap}
    except IndexError as e:
        logging.error(f"Failed to parse memory and swap usage: {e}")
        raise ValueError("Failed to parse memory and swap usage from stdout") from e
    except ValueError as e:
        logging.error(f"Failed to convert swap values to float: {e}")
        raise ValueError("Failed to convert swap values to float") from e

    return res

def omm_kill_parse(
    cmd: str,
    stdout: Any,
) -> Dict:
    if cmd != omm_kill_cmd:
        logging.error("Command is not 'omm_kill'.")
        raise ValueError("Command is not 'omm_kill'.")

    if not isinstance(stdout, str):
        logging.error("Input stdout is not a string.")
        raise TypeError("Expected stdout to be a string")

    try:
        omm_kill = float(stdout.split("\n")[0])
        res = {"omm_kill": omm_kill}
    except ValueError as e:
        logging.error(f"Failed to parse OOM killer count from stdout: {e}")
        raise ValueError("Failed to parse OOM killer count from stdout") from e

    return res

def sar_parse(
    cmd: str,
    stdout: Any,
) -> Dict:
    if cmd != "sar -r 1 1":
        logging.error("Command is not 'sar'.")
        raise ValueError("Command is not 'sar'.")

    if not isinstance(stdout, str):
        logging.error("Input stdout is not a string.")
        raise TypeError("Expected stdout to be a string")

    try:
        lines = stdout.split("\n")
        # Check if the header exists
        if not lines:
            raise ValueError("Output is empty")
        header = lines[2].strip().split()
        has_kbavail = "kbavail" in header
        out = stdout.split("\n")
        out.pop()  
        data = out[-1].split()
        if has_kbavail:
            memory_usage = float(data[4])  # memused at index 4 in sar version 10.1.5
        else:
            memory_usage = float(data[3])  # memused at index 3 in sar version 12.1.5
        res = {"memory_usage": memory_usage}
    except IndexError as e:
        logging.error(f"Failed to parse memory usage from sar output: {e}")
        raise ValueError("Failed to parse memory usage from sar output") from e
    except ValueError as e:
        logging.error(f"Failed to convert memory usage to float: {e}")
        raise ValueError("Failed to convert memory usage to float") from e

    return res

MEMORY_PARSE_FUNCTIONS = {
    "free": free_parse,
    omm_kill_cmd: omm_kill_parse,
    "sar -r 1 1": sar_parse,
}

class MemoryCollector(BaseCollector):
    def __init__(self, cmd: List[str], **kwargs):
        kwargs['cmds'] = cmd
        super().__init__(**kwargs)
    
    def parse_cmd_stdout(
        self,
        memory_info_stdout: Dict[str, Any],
    ) -> Dict:
        parse_result = {}
        for k, v in memory_info_stdout.items():
            # Use the dictionary to get the corresponding parse function; if cmd is not in the dict, use the default parse function
            parse_function = MEMORY_PARSE_FUNCTIONS.get(k, self.default_parse)
            cmd_parse_result = parse_function(k, v)
            parse_result = {**parse_result, **cmd_parse_result}
        return parse_result

    def calculate_swap_usage(
        self,
        available_swap: float,
        total_swap: float
    ) -> float:
        """Calculate swap usage rate"""
        if total_swap > 0:
            return 1 - (available_swap / total_swap)
        else:
            return 1

    def data_process(
        self,
        memory_parse_result: Dict,
    ) -> Dict:
        memory_process_result = {}
        
        # Calculate swap usage rate
        memory_process_result["swap_usage"] = self.calculate_swap_usage(
            memory_parse_result["available_swap_space"],
            memory_parse_result["total_swap_space"]
        )
        
        # Memory usage rate
        memory_process_result["memory_usage"] = memory_parse_result["memory_usage"] / 100
        
        # OOM Killer check
        memory_process_result["omm_kill"] = int(memory_parse_result["omm_kill"] > 0)
        
        return memory_process_result