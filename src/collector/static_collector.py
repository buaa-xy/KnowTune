import sys
import os
# Get the absolute path of the project root directory
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# Add the project root directory to sys.path
sys.path.append(project_root)

import subprocess
import re
from src.utils.shell_execute import remote_execute


def lscpu_parser(output: str) -> dict:
    metrics = {}
    for line in output.splitlines():
        if ":" not in line:
            continue
        k, v = [x.strip() for x in line.split(":", 1)]
        if k == "CPU(s)":
            metrics["CPU logical cores"] = int(v)
        elif k == "Core(s) per socket":
            metrics["Cores per physical CPU socket"] = int(v)
        elif k == "Socket(s)":
            metrics["Physical CPU sockets"] = int(v)
        elif k == "CPU MHz":
            metrics["cpu_mhz"] = float(v)
        elif k == "L3 cache":
            m = re.match(r"(\d+)\s*([KMG]i?B?)", v, re.IGNORECASE)
            if m:
                num = int(m.group(1))
                unit = m.group(2).upper()
                if unit in ("K", "KB", "KI", "KIB"):
                    bytes_val = num * 1024
                elif unit in ("M", "MB", "MI", "MIB"):
                    bytes_val = num * 1024**2
                elif unit in ("G", "GB", "GI", "GIB"):
                    bytes_val = num * 1024**3
                else:
                    bytes_val = num
                metrics["L3 cache size (bytes)"] = bytes_val
        elif k == "NUMA node(s)":
            metrics["NUMA nodes"] = int(v)
        elif k.startswith("NUMA node") and "CPU(s)" in k:
            key_name = k.lower().replace(" ", "_")
            metrics[key_name] = v
    return metrics


def free_parser(output: str) -> dict:
    metrics = {}
    lines = output.splitlines()
    for line in lines:
        parts = line.split()
        if len(parts) >= 7 and parts[0] == "Mem:":
            total_bytes = int(parts[1])
            total_gb = total_bytes / (1024**3)
            metrics["Total memory (GB)"] = round(total_gb, 2)
            used_bytes = int(parts[2])
            used_gb = used_bytes / (1024**3)
            metrics["Used memory (GB)"] = round(used_gb, 2)
            free_bytes = int(parts[3])
            free_gb = free_bytes / (1024**3)
            metrics["Free memory (GB)"] = round(free_gb, 2)
            available_bytes = int(parts[6])
            available_gb = available_bytes / (1024**3)
            metrics["Available memory (GB)"] = round(available_gb, 2)
    return metrics

def page_hugepages_parser(output: str) -> dict:
    metrics = {}
    lines = output.splitlines()
    if lines:
        metrics["System page size (bytes)"] = int(lines[0].strip())
    field_map = {
        "Total": "HugePages total",
        "Free": "HugePages free",
        "Rsvd": "HugePages reserved but unused",
        "Surp": "HugePages surplus",
    }
    for line in lines[1:]:
        m = re.match(r"HugePages_(\w+):\s+(\d+)", line)
        if m:
            key_en = field_map.get(m.group(1), f"HugePages_{m.group(1)}")
            metrics[key_en] = int(m.group(2))
    return metrics

def lsblk_parser(output: str) -> dict:
    metrics = {}
    for line in output.splitlines():
        name, rota, typ = line.split()
        if typ.lower() != "disk":
                continue
        t = "HDD" if rota == "1" else "SSD/NVMe"
        metrics[f"Disk {name} type"] = t
    return metrics

def iostat_parser(output: str) -> dict:
    metrics = {}
    lines = [l for l in output.splitlines() if l and not l.startswith("Linux") and not l.startswith("avg-cpu")]
    header_idx = None
    for i, l in enumerate(lines):
        if l.startswith("Device"):
            header_idx = i
    if header_idx is None:
        return metrics
    hdr = re.split(r"\s+", lines[header_idx].strip())
    for l in lines[header_idx + 1:]:
        cols = re.split(r"\s+", l.strip())
        if len(cols) != len(hdr):
            continue
        data = dict(zip(hdr, cols))
        dev = cols[0]
        metrics[f"{dev}_iops"] = float(data.get("r/s", 0)) + float(data.get("w/s", 0))
        metrics[f"{dev}_read_throughput_kB_s"] = float(data.get("rkB/s", 0))
        metrics[f"{dev}_write_throughput_kB_s"] = float(data.get("wkB/s", 0))
    return metrics

def queue_depth_parser(output: str) -> dict:
    metrics = {}
    for line in output.splitlines():
        path, val = line.split()
        dev = path.split("/")[3]
        metrics[f"Block device {dev} queue depth"] = int(val)
    return metrics

def raid_parser(output: str) -> dict:
    metrics = {}
    for line in output.splitlines():
        if line.startswith("md") and "raid" in line:
            m = re.search(r"raid(\d+)", line)
            if m:
                metrics[f"Array device {line.split()[0]} type"] = f"RAID{m.group(1)}"
    return metrics

def df_parser(output: str) -> dict:
    metrics = {}
    lines = output.splitlines()
    header = re.split(r"\s+", lines[0].strip()) if lines else []
    if not header:
        return metrics
    idx_fs = header.index("Type")
    idx_mnt = header.index("Mounted")
    for l in lines[1:]:
        cols = re.split(r"\s+", l.strip())
        fs, mnt = cols[idx_fs], cols[idx_mnt]
        metrics[f"fs_{mnt}"] = fs
    return metrics

def nic_queues_parser(output: str) -> dict:
    metrics = {}
    for line in output.splitlines():
        if "Combined:" in line:
            metrics["nic_combined_queues"] = int(line.split(':')[1].strip())
    return metrics

def ethtool_speed_parser(output: str) -> dict:
    metrics = {}
    m = re.search(r"Speed:\s*(\d+)([GM]b/s)", output)
    if m:
        metrics["Network speed"] = m.group(1) + m.group(2)
    return metrics

def sriov_parser(output: str) -> dict:
    metrics = {}
    for line in output.splitlines():
        if "SR-IOV" in line and "Total VFs:" in line:
            m = re.search(r"Total VFs:\s*(\d+)", line)
            if m:
                metrics["nic_sriov_total_vfs"] = int(m.group(1))
    return metrics

def fdlimit_parser(output: str) -> dict:
    return {"Max file descriptors": int(output.strip())}


def collect_system_profile(
    host_ip: str = "",
    host_port: int = 22,
    host_user: str = "root",
    host_password: str = "",
) -> dict:
    commands = [
        ("lscpu", lscpu_parser),
        ("free -b", free_parser),
        ("getconf PAGE_SIZE && grep HugePages_ /proc/meminfo", page_hugepages_parser),
        ("lsblk -dn -o NAME,ROTA,TYPE", lsblk_parser),
        ("iostat -dx -k 1 2", iostat_parser),
        ("for d in /sys/block/*/queue/nr_requests; do echo \"$d $(cat $d)\"; done", queue_depth_parser),
        ("cat /proc/mdstat", raid_parser),
        ("df -T -x tmpfs -x devtmpfs", df_parser),
        ("ethtool $(ls /sys/class/net | grep -v lo | head -n1)", nic_queues_parser),
        ("ethtool $(ls /sys/class/net | grep -v lo | head -n1)", ethtool_speed_parser),
        ("lspci -vv | grep -i sriov -A5", sriov_parser),
        ("ulimit -n", fdlimit_parser),
    ]
    all_metrics = {}
    for cmd, parser in commands:
        output = remote_execute(
            cmd=cmd,
            host_ip=host_ip,
            host_port=host_port,
            host_user=host_user,
            host_password=host_password,
        )
        if output and cmd in output:
            all_metrics.update(parser(output[cmd]))
        
    return all_metrics