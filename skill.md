---
name: system_tuning_skill
description: Execute step-by-step system performance tuning tasks using starttune.py functions. Use this skill when Claude needs to collect metrics, analyze bottlenecks, optimize parameters, and optionally generate strategy recommendations on target servers.
---

# System Tuning Skill

This skill allows Claude to perform automated system and application tuning by calling individual functions in `starttune.py` step by step.

## Instructions

Claude should trigger the following actions using command line calls to `starttune.py`:

1. **Collect static metrics**
```bash
python scripts/starttune.py collect_static_metrics --server <server_ip>
