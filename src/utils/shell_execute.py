import paramiko
from typing import Dict, Any, Callable
import logging
from functools import wraps, partial
from collections import defaultdict
from abc import abstractmethod
from types import ModuleType

decorated_funcs = defaultdict(list)
cmds_registry = defaultdict(list)


# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def remote_execute(
    cmd: str = "",
    host_ip: str = "",
    host_port: int = 22,
    host_user: str = "root",
    host_password: str = "",
) -> Dict[str, Any]:
    # Create SSH client instance
    client = paramiko.SSHClient()
    # Allow connecting to hosts not in known_hosts
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        # Connect to the remote host
        client.connect(host_ip, host_port, host_user, host_password)
        # Execute the command
        stdin, stdout, stderr = client.exec_command(cmd)
        # Get command execution result
        result = stdout.read().decode()
        error = stderr.read().decode()
        status_code = stdout.channel.recv_exit_status()
        
        if status_code:
            logging.error("Error executing command '%s': %s", cmd, error)
            return {cmd: result}
        else:
            logging.info("Command '%s' executed successfully.", cmd)
            return {cmd: result}
    except Exception as e:
        logging.error("Exception occurred while executing command '%s': %s", cmd, e)
        return None
    finally:
        # Close the SSH connection
        client.close()