# T27 operational amendment 01 — explicit isolated subnets

The first candidate preflight (`preflight-12b-v1`) could not create its Docker network: all predefined address pools were allocated. No 12B process or benchmark request ran. The attempt and normal-generator restoration are retained.

Use dedicated T27 subnets `10.254.27.0/24` (internal) and `10.254.28.0/24` (ingress). Existing Docker networks and host routes were inspected and do not overlap these ranges. Do not delete other projects' networks or data. This changes only isolated network provisioning, not models, memory settings, prompts or scoring. Retry under a new preflight run name after normal readiness is restored.
