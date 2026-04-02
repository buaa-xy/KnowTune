from .base_analyzer import BaseAnalyzer

class NetworkAnalyzer(BaseAnalyzer):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def analyze(self) -> str:
        report = "Based on the collected system metrics, the preliminary network performance analysis is as follows:\n"
        listenOverflows, fulldocookies, fulldrop, network_adapter = (
            self.data.get("listenOverflows", 0), 
            self.data.get("fulldocookies", 0),
            self.data.get("fulldrop", 0),
            self.data.get("network_interface_metrics", "")
        )
        report += self.listenOverflows_analysis(listenOverflows)
        report += self.fulldocookies_analysis(fulldocookies)
        report += self.fulldrop_analysis(fulldrop)
        report += self.network_adapter_analysis(network_adapter)
        return report
    
    def listenOverflows_analysis(
        self,
        listenOverflows: float
    ) -> str:
        return self.generate_report_line(listenOverflows == 1, 
            "The system has occurrences of TCP connections being dropped due to listen queue overflows. This usually indicates the system cannot handle incoming connection requests promptly, causing connections to be automatically dropped by the system."
        )

    def fulldrop_analysis(
        self,
        fulldrop: float
    ) -> str:
        return self.generate_report_line(fulldrop == 1, 
            "The system has occurrences of new TCP connection requests being dropped because the request queue is full. This usually indicates the system cannot handle incoming connection requests promptly, causing the kernel to automatically drop these requests."
        )

    def fulldocookies_analysis(
        self,
        fulldocookies: float
    ) -> str:
        return self.generate_report_line(fulldocookies == 1, 
            "The system has occurrences of sending SYN COOKIES because the TCP request queue is full. This usually indicates the system cannot handle incoming connection requests promptly, causing the kernel to take measures such as sending SYN COOKIES."
        )

    def network_adapter_analysis(
        self,
        network_adapter: str
    ) -> str:
        network_adapter_prompt = f"""
        # CONTEXT # 
        The current Linux system network interface data, performance metrics obtained from running 'netstat -i', is as follows:
        {network_adapter}

        # OBJECTIVE #
        Based on these performance metrics, generate a clear and logically structured system network performance summary report.
        Requirements:
        1. Analyze only the metrics that may impact system performance.
        2. Do not include any optimization suggestions.
        3. Preserve as much accurate and valid data from the information as possible.
        4. The answer should not exceed 200 words.

        # STYLE #
        You are a professional system operations expert. Your response should be logical, objective, concise, and clearly structured, making the answer reliable and credible.

        # TONE #
        Maintain a serious, careful, and rigorous tone.

        # AUDIENCE #
        Your answer will serve as an important reference for other system operations experts. Provide real and useful information; do not fabricate.

        # RESPONSE FORMAT #
        If there are multiple conclusions, list them with numbered points.

        """
        return self.ask_llm(network_adapter_prompt)
    
    def generate_report(
        self,
        network_report: str
    ) -> str:
        # TO DO
        # A report template is needed to indicate what information is included and the report format
        report_prompt = f"""
        The following content contains Linux system network performance information:
        {network_report}
        The data involved is accurate, reliable, and truthful.

        # OBJECTIVE #
        Analyze the system network performance based on the above information.
        Requirements:
        1. Do not include any optimization suggestions.
        2. Preserve as much accurate and valid data from the information as possible.
        3. Do not omit any information worth analyzing.

        # STYLE #
        You are a professional system operations expert. Your response should be logical, objective, concise, and clearly structured, making the answer reliable and credible.

        # TONE #
        Maintain a serious, careful, and rigorous tone.

        # AUDIENCE #
        Your answer will serve as an important reference for other system operations experts. Provide real and useful information; do not fabricate.

        # RESPONSE FORMAT #
        Start the answer with "Network analysis as follows:" and then list each analysis on a new line.
        If there are multiple conclusions, number them as separate points.
        
        """
        return self.ask_llm(report_prompt) + "\n"