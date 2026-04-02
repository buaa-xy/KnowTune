from .base_collector import BaseCollector
from typing import Dict, Any, List
import logging
import json
from enum import Enum
import re
import sys

class DiskMetric(Enum):
    TODO = "XX"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def get_disk_cmd()-> List[str]:
    return list(DISK_PARSE_FUNCTIONS.keys())
# 
def parse_iostat_dx_output(text: str) -> List[Dict[str, float]]:
    lines = text.strip().splitlines()

    # 找到最后一个 Device 行作为 headers
    device_indexes = [i for i, line in enumerate(lines) if line.strip().startswith("Device")]
    if not device_indexes:
        raise ValueError("No 'Device' header found in output.")
    
    header_index = device_indexes[-1]
    headers = re.split(r'\s+', lines[header_index].strip())

    # 修复 Device: -> Device
    if headers[0].startswith("Device"):
        headers[0] = "Device"

    entries = lines[header_index + 1:]

    disk_stats = []
    for line in entries:
        if not line.strip() or line.strip().startswith("Device"):
            continue
        fields = re.split(r'\s+', line.strip())
        if len(fields) < len(headers):
            continue

        record = {}
        for key, value in zip(headers, fields):
            try:
                record[key] = float(value) if key != "Device" else value
            except ValueError:
                record[key] = 0.0
        disk_stats.append(record)
    return disk_stats



def parse_disk_data_text(data: Dict[str, float]) -> Dict[str, Dict[str, float]]:
    device_name = data.get("Device") or data.get("device") or "unknown"
    r = data.get("r/s", 0.0)
    rkb = data.get("rkB/s") or data.get("kB_read/s") or 0.0
    w = data.get("w/s", 0.0)
    wkb = data.get("wkB/s") or data.get("kB_wrtn/s") or 0.0
    return {
        device_name: {
            "单位时间读速率": r,
            "单位时间读大小": rkb,
            "单位时间写速率": w,
            "单位时间写大小": wkb
        }
    }



def parse_disk_util_data_text(a_data: Dict[str, float], b_data: Dict[str, float]) -> Dict[str, Dict[str, float]]:
    device_name = b_data["Device"]
    wait = (
        b_data.get("r_await", 0.0) + b_data.get("w_await", 0.0) + b_data.get("d_await", 0.0)
        - a_data.get("r_await", 0.0) - a_data.get("w_await", 0.0) - a_data.get("d_await", 0.0)
    )
    aqu_sz = b_data.get("aqu-sz", 0.0) - a_data.get("aqu-sz", 0.0)
    util = b_data.get("util", 0.0)
    return {
        device_name: {
            "磁盘平均等待时间变化趋势": wait,
            "磁盘平均请求队列长度变化趋势": aqu_sz,
            "磁盘利用率": util
        }
    }


def iostat_text_parse(cmd: str, stdout: str) -> Dict:
    if cmd == "iostat -dx 1 2":
        parts = stdout.strip().split("\n\n")
        print(parts)
        if len(parts) < 2:
            raise ValueError("Expecting at least two outputs for `iostat -dx 1 2`.")
        second_sample = parse_iostat_dx_output(parts[-1])
        print(f"second_sample: {second_sample}")
        disk = [parse_disk_data_text(data) for data in second_sample]
        return {"磁盘读写性能": disk}

    elif cmd == "iostat -dx 1 2; sleep 5; iostat -dx 1 2":
        samples = stdout.strip().split("Device")
        samples = ["Device" + s for s in samples if s.strip()]
        if len(samples) < 4:
            raise ValueError("Expecting two full iostat blocks for comparison.")
        a_stats = parse_iostat_dx_output(samples[2])
        b_stats = parse_iostat_dx_output(samples[3])
        disk = [parse_disk_util_data_text(a, b) for a, b in zip(a_stats, b_stats)]
        return {"磁盘利用": disk}
    else:
        return {"error": "Unknown command"}

DISK_PARSE_FUNCTIONS = {
    "iostat -dx 1 2": iostat_text_parse,
    "iostat -dx 1 2; sleep 5; iostat -dx 1 2": iostat_text_parse,
}

class DiskCollector(BaseCollector):
    def __init__(self, cmd: List[str], **kwargs):
        kwargs['cmds'] = cmd
        super().__init__(**kwargs)
    
    def parse_cmd_stdout(
        self,
        disk_info_stdout: Dict[str, Any],
    ) -> Dict:
        parse_result = {}
        for k, v in disk_info_stdout.items():
            # 使用字典获取对应的解析函数，如果cmd不在字典中，使用默认的解析函数
            parse_function = DISK_PARSE_FUNCTIONS.get(k, self.default_parse)
            cmd_parse_result = parse_function(k, v)
            parse_result = {**parse_result, **cmd_parse_result}
        return parse_result

    def data_process(
        self,
        disk_parse_result: Dict,
    ) -> Dict:
        disk_process_result = {
            # "iowait": disk_parse_result["系统有未完成的磁盘I/O请求时，等待IO占用CPU的百分比"] / 100,
            "磁盘信息": disk_parse_result["磁盘利用"],
        }
        for i in range(len(disk_process_result["磁盘信息"])):
            for key in disk_process_result["磁盘信息"][i]:
                disk_process_result["磁盘信息"][i][key].update(disk_parse_result["磁盘读写性能"][i][key])
        
        return disk_process_result




    
