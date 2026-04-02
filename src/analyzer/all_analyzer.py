import sys
import os
# 获取项目根目录的绝对路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# 将项目根目录添加到 sys.path
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
        当前linux系统的性能分析报告如下,报告中所涉及到的数据准确无误,真实可信:
        {report}

        # OBJECTIVE #
        请根据系统性能分析报告,确定当前系统是否存在性能瓶颈;如果存在性能瓶颈,则该瓶
颈主要是存在于系统的哪个方面。
        你应该依据多条信息和多个指标的数据进行综合判断,不要基于单点信息轻易下结论,>你最终的结论应该能找到多个佐证。
        要求：
        1.你必须从[CPU,NETWORK,DISK,MEMORY,NONE]这五个选项中选择一项作为你的答案。
        2.不要回答多余的文字，你的答案必须严格和上述选项描述一致。
        3.如果你认为没有性能瓶颈,请选择NONE。

        # STYLE #
        你是一个专业的系统运维专家,你只用回答上述五个选项之一

        # Tone #
        你应该尽可能秉承严肃、认真、严谨的态度
        # AUDIENCE #
        你的答案将会是其他系统运维专家的重要参考意见，请认真思考后给出你的答案。

        # RESPONSE FORMAT #
        请直接回答五个选项之一,不要包含多余文字

        """
        result = self.ask_llm(bottle_neck_prompt)
        bottlenecks = {
            "cpu": "CPU",
            "disk": "DISK",
            "network": "NETWORK",
            "memory": "MEMORY",
            "none": "NONE"
        }

        # 转换为小写并查找瓶颈
        for key, value in bottlenecks.items():
            if key in result.lower():
                return value

        # 如果没有找到明确的瓶颈，返回UNKNOWN BOTTLENECKS
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
        return os_performance_report+app_performance_report, bottleneck

    def summarize_bottlenecks(
        self,
        report: str
    ) -> str:
        bottle_neck_prompt = f"""
        # CONTEXT #
        当前linux系统的性能分析报告如下,报告中所涉及到的数据准确无误,真实可信:
        {report}

        # OBJECTIVE #
        请根据系统性能分析报告,确定当前系统是否存在性能瓶颈;如果存在性能瓶颈,则该瓶
颈主要是存在于系统的哪个方面。
        你应该依据多条信息和多个指标的数据进行综合判断,不要基于单点信息轻易下结论,>你最终的结论应该能找到多个佐证。
        要求：
        1.你必须从[CPU,NETWORK,DISK,MEMORY,NONE]这五个选项中选择一项作为你的答案。
        2.不要回答多余的文字，你的答案必须严格和上述选项描述一致。
        3.如果你认为没有性能瓶颈,请选择NONE。

        # STYLE #
        你是一个专业的系统运维专家,你只用回答上述五个选项之一

        # Tone #
        你应该尽可能秉承严肃、认真、严谨的态度
        # AUDIENCE #
        你的答案将会是其他系统运维专家的重要参考意见，请认真思考后给出你的答案。

        # RESPONSE FORMAT #
        请直接回答五个选项之一,不要包含多余文字

        """
        result = self.ask_llm(bottle_neck_prompt)
        bottlenecks = {
            "cpu": "CPU",
            "disk": "DISK",
            "network": "NETWORK",
            "memory": "MEMORY",
            "none": "NONE"
        }

        # 转换为小写并查找瓶颈
        for key, value in bottlenecks.items():
            if key in result.lower():
                return value

        # 如果没有找到明确的瓶颈，返回UNKNOWN BOTTLENECKS
        return "UNKNOWN BOTTLENECKS"

if __name__ == "__main__":
    # data_network = {'Network': {'listenOverflows': 0, 'fulldocookies': 0, 'fulldrop': 0, '网卡指标': 'Linux 3.10.0-1160.119.1.el7.x86_64 (iZbp1fxgikakppqz32i5l7Z) \t05/26/2025 \t_x86_64_\t(2 CPU)\n\n02:21:10 PM     IFACE   rxpck/s   txpck/s    rxkB/s    txkB/s   rxcmp/s   txcmp/s  rxmcst/s\n02:21:11 PM      eth0      5.00      3.00      0.54      0.42      0.00      0.00      0.00\n02:21:11 PM        lo      3.00      3.00      0.28      0.28      0.00      0.00      0.00\n\nAverage:        IFACE   rxpck/s   txpck/s    rxkB/s    txkB/s   rxcmp/s   txcmp/s  rxmcst/s\nAverage:         eth0      5.00      3.00      0.54      0.42      0.00      0.00      0.00\nAverage:           lo      3.00      3.00      0.28      0.28      0.00      0.00      0.00\n'}}
    # data_cpu = {'Cpu': {'1min': 0.13, '5min': 0.045, '10min': 0.035, '用户态中的cpu利用率': 0.0101, '具有nice优先级的用户态CPU使用率': 0.0, 'kernel内核态执行时的CPU利用率': 0.01, '硬中断占用CPU时间的百分比': 0.0, '软中断占用CPU时间的百分比': 0.0, '虚拟化环境中，其他虚拟机占用的CPU时间百分比': 0.0, '运行虚拟处理器时CPU花费时间的百分比': 0.0, '运行带有nice优先级的虚拟CPU所花费的时间百分比': 0.0, 'CPU利用率': 0.015100000000000002, '系统每秒进行上下文切换的次数': 2023, '阻塞进程率': 0.0, '计算密集型': 0, 'IO密集型': 0, '进程信息': 'Linux 3.10.0-1160.119.1.el7.x86_64 (iZbp1fxgikakppqz32i5l7Z) \t05/26/2025 \t_x86_64_\t(2 CPU)\n\n02:20:39 PM   UID       PID   kB_rd/s   kB_wr/s kB_ccwr/s  Command\n02:20:39 PM     0         1      1.50      2.25      0.21  systemd\n02:20:39 PM     0        36      0.00      0.00      0.00  kswapd0\n02:20:39 PM     0       269      0.00      0.58      0.00  jbd2/vda1-8\n', '系统单位时间调用次数': 7515.0, 'cpu核数': 2}}
    # data_memory = {'Memory': {'交换空间使用率': 1, '内存使用率': 0.9501000000000001, 'omm_kill': 0}}
    # data_disk = {'Disk': {'磁盘信息': [{'vda': {'磁盘平均等待时间变化趋势': 7.07, '磁盘平均请求队列长度变化趋势': 0.0, '磁盘利用率': 0.0, '单位时间读速率': 0.0, '单位时间读大小': 0.0, '单位时间写速率': 0.0, '单位时间写大小': 0.0}}]}}
    
    data_network = {'Network': {'listenOverflows': 1, 'fulldocookies': 1, 'fulldrop': 1, '网卡指标': 'Linux 3.10.0-1160.119.1.el7.x86_64 (iZbp1fxgikakppqz32i5l7Z) \t05/26/2025 \t_x86_64_\t(2 CPU)\n\n02:21:10 PM     IFACE   rxpck/s   txpck/s    rxkB/s    txkB/s   rxcmp/s   txcmp/s  rxmcst/s\n02:21:11 PM      eth0     50.00     30.00      5.40      4.20      0.00      0.00      0.00\n02:21:11 PM        lo     30.00     30.00      2.80      2.80      0.00      0.00      0.00\n\nAverage:        IFACE   rxpck/s   txpck/s    rxkB/s    txkB/s   rxcmp/s   txcmp/s  rxmcst/s\nAverage:         eth0     50.00     30.00      5.40      4.20      0.00      0.00      0.00\nAverage:           lo     30.00     30.00      2.80      2.80      0.00      0.00      0.00\n'}}

    data_cpu = {'Cpu': {'1min': 1.5, '5min': 1.0, '10min': 0.8, '用户态中的cpu利用率': 0.75, '具有nice优先级的用户态CPU使用率': 0.05, 'kernel内核态执行时的CPU利用率': 0.15, '硬中断占用CPU时间的百分比': 0.02, '软中断占用CPU时间的百分比': 0.03, '虚拟化环境中，其他虚拟机占用的CPU时间百分比': 0.0, '运行虚拟处理器时CPU花费时间的百分比': 0.0, '运行带有nice优先级的虚拟CPU所花费的时间百分比': 0.0, 'CPU利用率': 0.95, '系统每秒进行上下文切换的次数': 12000, '阻塞进程率': 0.0, '计算密集型': 1, 'IO密集型': 1, '进程信息': 'Linux 3.10.0-1160.119.1.el7.x86_64 (iZbp1fxgikakppqz32i5l7Z) \t05/26/2025 \t_x86_64_\t(2 CPU)\n\n02:20:39 PM   UID       PID   kB_rd/s   kB_wr/s kB_ccwr/s  Command\n02:20:39 PM     0         1      1.50      2.25      0.21  systemd\n02:20:39 PM     0        36      0.00      0.00      0.00  kswapd0\n02:20:39 PM     0       269      0.00      0.58      0.00  jbd2/vda1-8\n', '系统单位时间调用次数': 12000.0, 'cpu核数': 2}}

    data_memory = {'Memory': {'交换空间使用率': 1, '内存使用率': 0.85, 'omm_kill': 0}}

    data_disk = {'Disk': {'磁盘信息': [{'vda': {'磁盘平均等待时间变化趋势': 20.0, '磁盘平均请求队列长度变化趋势': 5.0, '磁盘利用率': 0.96, '单位时间读速率': 100.0, '单位时间读大小': 10240.0, '单位时间写速率': 200.0, '单位时间写大小': 20480.0}}]}}
    
    data = {
    'Network': {
        'listenOverflows': 0,
        'fulldocookies': 0,
        'fulldrop': 0,
        '网卡指标': 'Linux 3.10.0-1160.119.1.el7.x86_64 (iZbp1fxgikakppqz32i5l7Z) \t05/26/2025 \t_x86_64_\t(2 CPU)\n\n02:21:10 PM     IFACE   rxpck/s   txpck/s    rxkB/s    txkB/s   rxcmp/s   txcmp/s  rxmcst/s\n02:21:11 PM      eth0     50.00     30.00      5.40      4.20      0.00      0.00      0.00\n02:21:11 PM        lo     30.00     30.00      2.80      2.80      0.00      0.00      0.00\n\nAverage:        IFACE   rxpck/s   txpck/s    rxkB/s    txkB/s   rxcmp/s   txcmp/s  rxmcst/s\nAverage:         eth0     50.00     30.00      5.40      4.20      0.00      0.00      0.00\nAverage:           lo     30.00     30.00      2.80      2.80      0.00      0.00      0.00\n'
    },
    'Cpu': {
        '1min': 1.5,
        '5min': 1.0,
        '10min': 0.8,
        '用户态中的cpu利用率': 0.75,
        '具有nice优先级的用户态CPU使用率': 0.05,
        'kernel内核态执行时的CPU利用率': 0.15,
        '硬中断占用CPU时间的百分比': 0.02,
        '软中断占用CPU时间的百分比': 0.03,
        '虚拟化环境中，其他虚拟机占用的CPU时间百分比': 0.0,
        '运行虚拟处理器时CPU花费时间的百分比': 0.0,
        '运行带有nice优先级的虚拟CPU所花费的时间百分比': 0.0,
        'CPU利用率': 0.95,
        '系统每秒进行上下文切换的次数': 12000,
        '阻塞进程率': 0.0,
        '计算密集型': 1,
        'IO密集型': 1,
        '进程信息': 'Linux 3.10.0-1160.119.1.el7.x86_64 (iZbp1fxgikakppqz32i5l7Z) \t05/26/2025 \t_x86_64_\t(2 CPU)\n\n02:20:39 PM   UID       PID   kB_rd/s   kB_wr/s kB_ccwr/s  Command\n02:20:39 PM     0         1      1.50      2.25      0.21  systemd\n02:20:39 PM     0        36      0.00      0.00      0.00  kswapd0\n02:20:39 PM     0       269      0.00      0.58      0.00  jbd2/vda1-8\n',
        '系统单位时间调用次数': 12000.0,
        'cpu核数': 2
    },
    'Memory': {
        '交换空间使用率': 1,
        '内存使用率': 0.85,
        'omm_kill': 0
    },
    'Disk': {
        '磁盘信息': [{
            'vda': {
                '磁盘平均等待时间变化趋势': 20.0,
                '磁盘平均请求队列长度变化趋势': 5.0,
                '磁盘利用率': 0.96,
                '单位时间读速率': 100.0,
                '单位时间读大小': 10240.0,
                '单位时间写速率': 200.0,
                '单位时间写大小': 20480.0
            }
        }]
    }
}
    
    analyzer = Analyzer(
        data=data
    )
    print(analyzer.run())