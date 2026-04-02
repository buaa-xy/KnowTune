from .base_analyzer import BaseAnalyzer

class MemoryAnalyzer(BaseAnalyzer):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
    
    def analyze(self) -> str:
        report = "Preliminary memory performance analysis based on collected system metrics:\n"
        swapout, oom_kill, swap_ratio, util = (
            self.data.get("swapout", 0), 
            self.data.get("omm_kill", 0),
            self.data.get("swap_usage", 0),
            self.data.get("memory_usage", 0)
        )
        swap_ratio = 1 - swap_ratio
        report += f"System memory usage is {util}\n"
        report += self.omm_kill_analysis(oom_kill)
        report += self.swap_analysis(swap_ratio)
        report += self.swapout_analysis(swapout)
        return report
    
    def omm_kill_analysis(
        self,
        oom_kill: float,
    ) -> str:
        return self.generate_report_line(
            oom_kill == 1, 
            "An OOM kill has recently occurred in the system, indicating severe memory shortage that required terminating processes to free memory."
        )
    
    def swap_analysis(
        self,
        swap_low: float,
    ) -> str:
        return self.generate_report_line(
            swap_low < 0.1, 
            f"The available swap space is {swap_low}, which is below the predefined threshold. The system may soon run out of virtual memory. Consider reducing the number or size of running processes or increasing swap space to avoid full exhaustion."
        )
    
    def swapout_analysis(
        self,
        swapout: float,
    ) -> str:
        return self.generate_report_line(
            swapout == 1, 
            "The system is continuously swapping pages to swap space at a high rate, indicating that physical memory may be insufficient."
        )
    
    def generate_report(
        self,
        memory_report: str
    ) -> str:
        # TO DO
        # A report template should be defined, specifying which information to include and the report format
        report_prompt = f"""
        The following content provides memory-related performance information on the Linux system:
        {memory_report}
        The data presented is accurate and reliable.

        # OBJECTIVE #
        Based on the information above, analyze the system's memory performance.
        Requirements:
        1. Do not include any optimization suggestions in the answer.
        2. Retain the authentic and valid data as much as possible.
        3. Do not omit any information worth analyzing.

        # STYLE #
        You are a professional system administrator. Your response should be logically rigorous, objective, concise, and clear, providing trustworthy insights.

        # TONE #
        Maintain a serious, careful, and rigorous attitude throughout the answer.

        # AUDIENCE #
        Your response will serve as a reference for other system administrators. Provide useful and factual information; do not fabricate data.

        # RESPONSE FORMAT #
        Begin the response with "Memory analysis as follows:" and list the analyses line by line.
        If there are multiple analysis points, number them sequentially.
        """
        return self.ask_llm(report_prompt) + "\n"