from pydantic import BaseModel  # Used to define and validate input parameter models
from abc import abstractmethod  # Used to declare abstract methods in the base class, requiring subclasses to implement
from typing import Dict, List, Any
from src.utils.shell_execute import remote_execute

class CollectorArgs(BaseModel):
    cmds: List[str] = []
    host_ip: str = ""
    host_port: int = 22
    host_user: str = "root"
    host_password: str = ""

class BaseCollector:
    def __init__(self, **kwargs):
        # Initialize args using the constructor of the pydantic model
        self.args = CollectorArgs(**kwargs)

    def get_cmd_stdout(
        self,
    ) -> Dict:
        # Execute remote commands
        result = {}
        for cmd in self.args.cmds:
            cmd_res = remote_execute(
                cmd=cmd,
                host_ip=self.args.host_ip,
                host_port=self.args.host_port,
                host_user=self.args.host_user,
                host_password=self.args.host_password,
            )
            result = {**result, **cmd_res}
        return result

    @abstractmethod
    def parse_cmd_stdout(self, **kwargs) -> Dict:
        # Abstract method to parse command output, must be implemented by subclasses
        pass

    def default_parse(
        self,
        cmd: str,
        stdout: Any,
    ) -> Dict:
        # Default parser returns a dictionary with the command as key and stdout as value
        return {cmd: stdout}
    
    @abstractmethod
    def data_process(self, **kwargs) -> Dict:
        # Abstract method to process parsed data, must be implemented by subclasses
        pass

    def run(self) -> Dict:
        # 1. Get the command execution results
        cmd_stdout = self.get_cmd_stdout()

        # 2. Parse the command output
        parsed_data = self.parse_cmd_stdout(cmd_stdout)

        # 3. Process the parsed data
        processed_data = self.data_process(parsed_data)

        # 4. Return the processed data
        return processed_data