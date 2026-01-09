---
name: copilot_tuning_skill
description: Execute full system performance tuning workflow using A-Tune. The skill automatically sets the target server information in config, activates the virtual environment, and runs start_tune.py.
---

# System Tuning Skill

This skill allows Claude to perform **automated full system tuning** by executing `start_tune.py` in one command.

**Keywords**: system tuning, performance optimization, parameter optimization, metrics collection, runtime metrics, static metrics, bottleneck analysis, MySQL tuning, server optimization, strategy recommendations

## Instructions

Claude should trigger the following actions using command line calls:

1. **Navigate to the skill directory**
- The `A-Tune` directory is located in the **same directory as this `skill.md` file**.  
- Change to the `A-Tune` directory:
```bash
cd ./A-Tune
```
