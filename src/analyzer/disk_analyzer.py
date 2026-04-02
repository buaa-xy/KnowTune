from .base_analyzer import BaseAnalyzer

class DiskAnalyzer(BaseAnalyzer):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def analyze(self) -> str:
        report = "Based on the collected system metrics, the preliminary disk performance analysis report is as follows: \n"
        disks_info, iowait = self.data.get("disk_info", {})[0], self.data.get("iowait", 0)
        report += f"The system iowait value is {iowait}\n"
        for disk_name, disk_info in disks_info.items():
            wait_time, queue_length, util, read_speed, write_speed, read_size, write_size = (
                disk_info.get("avg_disk_wait_time_trend", 0),
                disk_info.get("avg_disk_request_queue_len_trend", 0),
                disk_info.get("disk_utilization", 0),
                disk_info.get("read_rate_per_sec", 0),
                disk_info.get("write_rate_per_sec", 0),
                disk_info.get("read_size_per_sec", 0),
                disk_info.get("write_size_per_sec", 0),
            )
            report += f"Basic information for disk {disk_name}:\n"
            report += f"Disk utilization is {util}, read speed is {read_speed}, write speed is {write_speed}\n"
            report += self.disk_info_analysis(wait_time, queue_length, util)
            report += self.disk_rw_analysis(read_speed, write_speed, read_size, write_size, util)
        return report
    
    def disk_info_analysis(
        self,
        wait_time: float,
        queue_length: float,
        util: float,
    ) -> str:
        disk_info_report = ""
        queue_length_message = (
            "The disk device request queue length is increasing and the device utilization exceeds the preset threshold, which may indicate the disk is approaching or has reached its processing capacity limit."
            if queue_length > 0 and util > 0.90
            else ""
        )
        disk_info_report += self.generate_report_line(queue_length_message, queue_length_message)

        wait_time_message = (
            "The disk device request processing speed is decreasing and the device utilization exceeds the preset threshold, which may indicate the disk is approaching or has reached its processing capacity limit."
            if wait_time > 0 and util > 0.90
            else ""
        )
        disk_info_report += self.generate_report_line(wait_time_message, wait_time_message)
        return disk_info_report

    def disk_rw_analysis(
        self,
        read_speed: float,
        write_speed: float,
        read_size: float,
        write_size: float,
        util: float,
    ) -> str:
        disk_rw_report = ""
        read_size = read_size / 1024
        write_size = write_size / 1024

        iops_message = (
            "The disk average Input/Output Operations Per Second (IOPS) exceeds the preset limit and device utilization exceeds the preset threshold, which may indicate the disk is approaching or has reached its processing capacity limit."
            if read_speed + write_speed > 120 and util > 0.90
            else ""
        )
        disk_rw_report += self.generate_report_line(iops_message, iops_message)

        size_message = (
            "The disk average transfer rate exceeds the preset bandwidth limit and device utilization exceeds the preset threshold, which may indicate the disk is approaching or has reached its processing capacity limit."
            if read_size + write_size > 100 and util > 0.90
            else ""
        )
        disk_rw_report += self.generate_report_line(size_message, size_message)

        return disk_rw_report
    
    def generate_report(
        self,
        disk_report: str
    ) -> str:
        # TO DO
        # Need a report template specifying included information and report format
        report_prompt = f"""
        The following content contains disk-related performance information in a Linux system:
        {disk_report}
        All data involved is accurate and trustworthy.

        # OBJECTIVE #
        Please analyze the system's disk performance based on the above information.
        Requirements:
        1. Do not include any optimization suggestions.
        2. Retain as much accurate and valid data as possible.
        3. Do not omit any information worth analyzing.

        # STYLE #
        You are a professional system administrator. Your answer should be logically rigorous, objective, concise, and clear, making the response trustworthy.

        # TONE #
        You should maintain a serious, professional, and rigorous attitude.

        # AUDIENCE #
        Your answer will serve as an important reference for other system administrators, so please provide truthful and useful information without fabrication.

        # RESPONSE FORMAT #
        Start the answer with "Disk analysis as follows:", then list each analysis point on a new line.
        If there are multiple conclusions, number them sequentially.
        
        """
        return self.ask_llm(report_prompt) + "\n"