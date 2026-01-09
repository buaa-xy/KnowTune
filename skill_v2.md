---
name: copilot_tuning_skill
description: Execute full system performance tuning workflow using A-Tune. The skill automatically sets the target server information in config, activates the virtual environment, and runs start_tune.py.
---

# Copilot Tuning Skill

This skill allows Agent to perform **automated full system tuning** by executing `start_tune.py` in one command.

**Keywords**: system tuning, performance optimization, parameter optimization, metrics collection, runtime metrics, static metrics, bottleneck analysis, MySQL tuning, server optimization, strategy recommendations

## Instructions

Agent should trigger the following actions using command line calls:

1. **Navigate to the skill directory**
- The `A-Tune` directory is located in the **same directory as this `skill.md` file**.  
- Change to the `A-Tune` directory:
```bash
cd ./A-Tune
```

2. **Activate the virtual environment**
```bash
source venv/bin/activate
```

3. **Update target server information**
- Agent should read the user input containing server connection details:
  - `ip`
  - `user`
  - `password`
- **Validation:**  
  - If any of these values are missing, the skill **must stop** and indicate which information is missing, asking the user to provide it.  
  - Example message:  
    > "Missing server IP. Please provide the target server's IP, username, and password before proceeding."
- **Update `.env.yaml`**  
  - If all values are provided, Agent should update the `servers[0]` entry in `config/.env.yaml` accordingly.  
  - Fields to update:
    - `ip` → user-provided server IP
    - `host_user` → user-provided username
    - `password` → user-provided password
  - Ensure that YAML structure and indentation are preserved when making changes.
 
4. **Run the full system tuning script**
- Agent should execute the main tuning script:
```bash
python src/start_tune.py
```
- Note: This single command will automatically perform all tuning steps, including:
  - Metric collection
  - Bottleneck analysis
  - Parameter optimization
  - Optional strategy recommendations
 
5. **Read tuning log and summarize results**
- After the tuning process finishes, a directory named `tuning.log` will be generated under the current working directory.
- Claude should read the contents of `tuning.log` (including key logs, final configuration, and performance results).
- Based on the log contents, Agent should:
  - Summarize the tuning process
  - Explain identified bottlenecks and corresponding optimization actions
  - Highlight performance improvements (e.g., QPS, latency, resource utilization)
  - Provide a concise tuning conclusion

## Example

**Input:**  
Optimize MySQL performance on server `192.168.1.10` using the full automatic tuning workflow.  
SSH connection information (IP, user, password) is provided by the user.

**Output:**  

- Full system tuning process executed via `start_tune.py`
- Metrics collection, bottleneck analysis, and parameter optimization completed automatically
- A `tuning_log` directory generated after execution
- Final tuning summary produced based on `tuning_log`, including:
  - Identified performance bottlenecks
  - Key optimized parameters
  - Observed performance improvements
  - Overall tuning conclusions and recommendations
