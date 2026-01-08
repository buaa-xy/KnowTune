---
name: system_tuning_skill
description: Execute step-by-step system performance tuning tasks using starttune.py functions. Use this skill when Claude needs to collect metrics, analyze bottlenecks, optimize parameters, and optionally generate strategy recommendations on target servers.
---

# System Tuning Skill

This skill allows Claude to perform automated system and application tuning by calling individual functions in `starttune.py` step by step.
**Keywords**: system tuning, performance optimization, parameter optimization, metrics collection, runtime metrics, static metrics, micro-dependency analysis, pressure testing, bottleneck analysis, MySQL tuning, server optimization, strategy recommendations

## Instructions

Claude should trigger the following actions using command line calls to `starttune.py`:

1. **Collect static metrics**
```bash
python scripts/starttune.py collect_static_metrics --server <server_ip>
```

2. **Collect runtime metrics**
```bash
python scripts/starttune.py collect_runtime_metrics --server <server_ip> [--pressure]
```

3. **Collect micro-dependencies (optional)**
```bash
python scripts/starttune.py collect_micro_dependencies --server <server_ip> [--iterations N]
```

4. **Analyze performance**
```bash
python scripts/starttune.py analyze_performance --server <server_ip>
```

5. **Optimize parameters**
```bash
python scripts/starttune.py optimize_params --server <server_ip> [--iterations N]
```

6. **Run strategy optimization (optional)**
```bash
python scripts/starttune.py strategy_optimization --server <server_ip>
```

## Notes

- `<server_ip>` should match the target server configured in `config`.
- Optional arguments:
  - `--pressure` enables pressure test during runtime metrics collection.
  - `--iterations` specifies iterations for micro-dependency collection or parameter optimization.

## Example

**Input:**  
"Optimize MySQL performance on server 192.168.1.10 using full system tuning workflow."

**Output:**  
- Static system metrics collected  
- Runtime metrics collected with optional pressure test  
- Micro-dependency analysis (if enabled)  
- Performance bottleneck analysis completed  
- Parameter optimization executed and best config saved  
- Optional strategy optimization recommendations

