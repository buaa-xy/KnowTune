from .base_analyzer import BaseAnalyzer

class CpuAnalyzer(BaseAnalyzer):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
    
    def analyze(self) -> str:
        report = "Based on the collected system metrics, the preliminary CPU performance analysis is as follows:\n"
        avg_load_report = self.avg_load_analysis()
        cpu_info_report = self.cpu_info_analysis()
        #pid_info_report = self.pid_info_analysis()

        report += avg_load_report
        report += cpu_info_report
        #report += pid_info_report

        return report

    def avg_load_analysis(self) -> str:
        avg_load_analysis_report = ""

        # Extract CPU average load data
        one_min, five_min, ten_min = self.data.get("1min", 0.0), self.data.get("5min", 0.0), self.data.get("10min", 0.0)

        # Generate average load report
        avg_load_analysis_report += f"The current system 1-minute average load is {one_min}, 5-minute average load is {five_min}, 10-minute average load is {ten_min}\n"

        # Generate report lines
        avg_load_analysis_report += (
            self.generate_report_line(one_min > 1, "The system load in the past 1 minute is high, which may indicate a CPU performance bottleneck")
        )
        avg_load_analysis_report += (
            self.generate_report_line(five_min > 1, "The system load in the past 5 minutes is high, which may indicate a CPU performance bottleneck")
        )
        avg_load_analysis_report += (
            self.generate_report_line(ten_min > 1, "The system load in the past 10 minutes is high, which may indicate a CPU performance bottleneck")
        )

        # Check for sudden load increase
        sudden_increase_message = (
            "The system load in the past 1 minute has increased sharply, CPU performance demand may rise"
            if (one_min > 2 * five_min or one_min > 2 * ten_min) and one_min > 1
            else ""
        )
        avg_load_analysis_report += self.generate_report_line(sudden_increase_message, sudden_increase_message)

        # Check load stability
        stability_message = (
            "System load has been relatively stable over the past 10 minutes, with no significant fluctuations"
            if abs(one_min - five_min) <= 0.2 and abs(one_min - ten_min) <= 0.2 and abs(five_min - ten_min) <= 0.2
            else "System load has experienced some fluctuations over the past 10 minutes"
        )
        avg_load_analysis_report += self.generate_report_line(stability_message, stability_message)

        # Check load trend
        trend_message = (
            "System load has been continuously increasing over the past 10 minutes, CPU performance demand may rise"
            if one_min - five_min > 0.2 and five_min - ten_min > 0.2 and one_min > 0.5
            else ""
        )
        avg_load_analysis_report += self.generate_report_line(trend_message, trend_message)

        return avg_load_analysis_report
    
    def cpu_info_analysis(self) -> str:
        cpu_info_analysis_report = ""

        # Extract CPU information data
        usr, sys, irq, soft, util = (
            self.data.get("user_mode_cpu_utilization", 0),
            self.data.get("kernel_cpu_utilization", 0),
            self.data.get("hardware_interrupt_percentage", 0),
            self.data.get("software_interrupt_percentage", 0),
            self.data.get("overall_cpu_utilization", 0)
        )
        block_process, cpu_load, io_load = (
            self.data.get("blocked_process_ratio", 0),
            self.data.get("compute_intensive", 0),
            self.data.get("io_intensive", 0)
        )
        context_switch, sys_call, cpu_num = (
            self.data.get("context_switch_per_sec", 0),
            self.data.get("system_calls_per_sec", 0),
            self.data.get("cpu_cores", 1)  # Default to 1 to avoid division by zero
        )

        # Build basic information report
        cpu_info_analysis_report += (
            f"In the current system, user-mode CPU utilization: {usr*100}%, kernel-mode CPU utilization: {sys*100}%, "
            f"hardware interrupt percentage: {irq*100}%, software interrupt percentage: {soft*100}%, overall CPU utilization: {util*100}%\n"
        )

        # Generate other report lines based on conditions
        conditions_and_messages = [
            (usr + sys + irq + soft > 0.9, "The system load is high, which may indicate a CPU bottleneck."),
            (cpu_load == 1, "User-mode CPU utilization is much higher than kernel-mode, indicating compute-intensive workloads."),
            (io_load == 1, "High kernel-mode system call frequency indicates I/O-intensive workload characteristics."),
            (context_switch > cpu_num * 4000, f"Context switches per second are {context_switch}, exceeding normal threshold, which may degrade performance."),
            (sys_call > cpu_num * 10000, f"System call rate per second is {sys_call}, indicating heavy system calls likely due to high load or resource-intensive applications."),
            ((usr + sys) > 0.7 and sys > (0.75 * usr + 0.75 * sys), "System processing capacity in kernel mode may be insufficient, possibly causing longer response times or performance degradation."),
            (sys_call < 100 and util > 0.5, "There are currently many processes with floating point exceptions (FPEs)."),
        ]

        for condition, message in conditions_and_messages:
            cpu_info_analysis_report += self.generate_report_line(condition, message)

        # Add blocked process report
        cpu_info_analysis_report += f"The proportion of blocked processes is {block_process}%\n"

        return cpu_info_analysis_report
    
    def pid_info_analysis(self) -> str:
        pid_info_report = "Based on the collected system metrics, the preliminary system process performance analysis is as follows:\n"
        pid_prompt = """
        # CONTEXT # 
        Linux system process data is available, with performance metrics obtained from executing 'pidstat -d | head -6' in Linux, as follows:
        {pid_info}

        # OBJECTIVE #
        Please generate a clear and logical performance summary report of the system processes based on these metrics.
        Requirements:
        1. Only analyze metrics that may affect system performance.
        2. Do not include any optimization suggestions.
        3. Retain as much accurate data as possible.
        4. Limit response to 200 words.

        # STYLE #
        You are a professional system operations expert. Your response should be logical, objective, concise, clear, and credible.

        # TONE #
        Maintain a serious, professional, and rigorous tone.

        # AUDIENCE #
        Your answer will be used as an important reference by other system administrators, so provide accurate and useful information.

        # RESPONSE FORMAT #
        If multiple conclusions exist, number them sequentially.
        
        """
        pid_info = self.data["process_info"]
        pid_info_report += self.ask_llm(pid_prompt.format(pid_info=pid_info))
        return pid_info_report
    
    def generate_report(
        self,
        cpu_report: str
    ) -> str:
        # TODO
        # Provide a report template specifying included information and format
        report_prompt = f"""
        The following content contains CPU-related performance information in a Linux system:
        {cpu_report}
        The data involved is accurate and reliable.

        # OBJECTIVE #
        Analyze the CPU performance based on the above information.
        Requirements:
        1. Do not include any optimization suggestions.
        2. Retain as much accurate data as possible.
        3. Do not omit any relevant information.

        # STYLE #
        You are a professional system operations expert. Your response should be logical, objective, concise, clear, and credible.

        # TONE #
        Maintain a serious, professional, and rigorous tone.

        # AUDIENCE #
        Your answer will be used as an important reference by other system administrators, so provide accurate and useful information.

        # RESPONSE FORMAT #
        Start with "CPU analysis as follows:" on a new line, then list points sequentially.
        Number multiple conclusions sequentially.
        
        """
        return self.ask_llm(report_prompt) + "\n"