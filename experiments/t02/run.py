"""Host-side Docker/GPU measurement; inference itself stays in offline containers."""

import argparse
import csv
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import threading
import time


ROOT = Path(__file__).resolve().parents[2]
COMPOSE = ["docker", "compose", "--project-name", "vectornext-t02", "-f", str(ROOT / "compose.models.yaml")]
NO_WINDOW = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


def command(args, timeout=300, check=True):
    result = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, creationflags=NO_WINDOW)
    if check and result.returncode:
        raise RuntimeError(f"Command failed ({result.returncode}): {' '.join(args)}\n{result.stdout}\n{result.stderr}")
    return result


def gpu_snapshot():
    result = command(["nvidia-smi", "--query-gpu=name,memory.total,memory.used,driver_version", "--format=csv,noheader,nounits"])
    return result.stdout.strip()


def run(keep_running=False, variant="e2b", schema_mode="legacy"):
    compose = COMPOSE
    if variant == "26b":
        compose = ["docker", "compose", "--project-name", "vectornext-t02-26b", "-f", str(ROOT / "compose.models.yaml"), "-f", str(ROOT / "compose.models.26b.yaml")]
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    directory = ROOT / "data/t02" / run_id
    directory.mkdir(parents=True)
    report = {"run_id": run_id, "variant": variant, "schema_mode": schema_mode, "scope": "process-cold startup; OS file cache not flushed; images/models already acquired", "gpu_sampling_requested_ms": 200}
    gpu_thread = None
    stop_sampling = threading.Event()
    sample_times = []
    sample_errors = []
    gpu_stream = None
    try:
        report["git_revision"] = command(["git", "rev-parse", "HEAD"]).stdout.strip()
        report["git_dirty"] = bool(command(["git", "status", "--porcelain"]).stdout.strip())
        report["docker_version"] = command(["docker", "version", "--format", "{{.Server.Version}}"]).stdout.strip()
        report["gpu_container_probe"] = command(compose + ["run", "--rm", "--no-deps", "gpu-check"]).stdout.strip()
        report["artifact_verification"] = command(compose + ["run", "--rm", "--no-deps", "model-check", "python", "-m", "experiments.t02.fetch_models", "--verify-only"], timeout=600).stdout.strip()
        # A dedicated Compose project makes restarts/cleanup specific to this experiment.
        command(compose + ["stop", "llm"])
        report["gpu_before"] = gpu_snapshot()
        gpu_stream = (directory / "gpu.csv").open("w", encoding="utf-8")

        def sample_gpu():
            while not stop_sampling.is_set():
                try:
                    sample = command(["nvidia-smi", "--query-gpu=timestamp,memory.used,utilization.gpu", "--format=csv,noheader,nounits"], timeout=10)
                    gpu_stream.write(sample.stdout)
                    gpu_stream.flush()
                    sample_times.append(time.perf_counter())
                except Exception as error:
                    sample_errors.append(str(error))
                stop_sampling.wait(0.2)

        gpu_thread = threading.Thread(target=sample_gpu, daemon=True)
        gpu_thread.start()
        start = time.perf_counter()
        command(compose + ["up", "-d", "--force-recreate", "llm"])
        container = command(compose + ["ps", "-q", "llm"]).stdout.strip()
        while True:
            inspection = json.loads(command(["docker", "inspect", container]).stdout)[0]
            state = inspection["State"]
            if state.get("Health", {}).get("Status") == "healthy":
                break
            if not state["Running"] or time.perf_counter() - start > (600 if variant == "26b" else 240):
                raise RuntimeError("Generation container failed readiness; inspect server.log")
            time.sleep(0.5)
        report["container_start_to_healthy_seconds"] = time.perf_counter() - start
        report["readiness_observation"] = "Docker healthcheck every 2s plus host polling every 0.5s; includes creation and runtime warmup"
        report["llm_image_id"] = inspection["Image"]
        report["llm_command"] = inspection["Config"]["Cmd"]
        report["llm_mounts"] = [{"destination": m["Destination"], "type": m["Type"], "rw": m["RW"]} for m in inspection["Mounts"]]
        network_names = list(inspection["NetworkSettings"]["Networks"])
        report["networks"] = [{"name": n, "internal": json.loads(command(["docker", "network", "inspect", n]).stdout)[0]["Internal"]} for n in network_names]
        if not report["networks"] or not all(n["internal"] for n in report["networks"]):
            raise RuntimeError("Runtime has a network with external connectivity")
        startup = command(compose + ["logs", "--no-color", "llm"])
        offload = re.search(r"offloaded (\d+)/(\d+) layers to GPU", startup.stdout + startup.stderr)
        if not offload or int(offload.group(1)) == 0:
            raise RuntimeError("No positive GPU layer-offload evidence in startup logs")
        report["gpu_layers_offloaded"] = int(offload.group(1))
        report["gpu_layers_total"] = int(offload.group(2))
        print(f"GPU runtime healthy after {report['container_start_to_healthy_seconds']:.2f}s", flush=True)
        check = command(compose + ["run", "--rm", "--no-deps", "model-check", "python", "-m", "experiments.t02.benchmark", "--schema-mode", schema_mode, "--output", f"/results/{run_id}/models.json"], timeout=1800 if variant == "26b" else 600, check=False)
        (directory / "check.log").write_text(check.stdout + check.stderr, encoding="utf-8")
        print(check.stdout, flush=True)
        report["check_exit_code"] = check.returncode
        report["cpu_image_id"] = command(["docker", "image", "inspect", "vectornext-model-check:t02", "--format", "{{.Id}}"]).stdout.strip()
        peak = command(compose + ["exec", "-T", "llm", "python", "-c", "from pathlib import Path; print(Path('/sys/fs/cgroup/memory.peak').read_text().strip())"], check=False)
        report["llm_cgroup_memory_peak_bytes"] = int(peak.stdout.strip()) if peak.returncode == 0 else None
        if check.returncode:
            raise RuntimeError("Model checks failed; inspect models.json and check.log")
    except Exception as error:
        report["error"] = str(error)
        raise
    finally:
        logs = command(compose + ["logs", "--no-color", "llm"], check=False)
        (directory / "server.log").write_text(logs.stdout + logs.stderr, encoding="utf-8")
        report["cuda_log_evidence"] = [line for line in (logs.stdout + logs.stderr).splitlines() if any(term in line for term in ["CUDA0", "offloaded", "n_ctx_per_seq", "CUDA :", "model loaded", "CPU_Mapped", "CPU model buffer"])]
        if not keep_running:
            command(compose + ["stop", "llm"], check=False)
        stop_sampling.set()
        if gpu_thread is not None:
            gpu_thread.join(timeout=12)
        if gpu_stream is not None:
            gpu_stream.close()
            rows = list(csv.reader((directory / "gpu.csv").read_text().splitlines()))
            samples = [int(row[1].strip()) for row in rows if len(row) == 3 and row[1].strip().isdigit()]
            report["gpu_samples"] = len(samples)
            report["gpu_sampling_errors"] = sample_errors
            report["gpu_sample_interval_max_seconds"] = max((b - a for a, b in zip(sample_times, sample_times[1:])), default=None)
            report["whole_device_peak_used_mib"] = max(samples) if samples else None
            utilization = [int(row[2].strip()) for row in rows if len(row) == 3 and row[2].strip().isdigit()]
            report["whole_device_peak_utilization_percent"] = max(utilization) if utilization else None
        report["gpu_after"] = gpu_snapshot()
        report["service_left_running"] = keep_running
        (directory / "host.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"Results: {directory}", flush=True)
    return directory


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--keep-running", action="store_true")
    parser.add_argument("--variant", choices=["e2b", "26b"], default="e2b")
    parser.add_argument("--schema-mode", choices=["legacy", "status"], default="legacy")
    args = parser.parse_args()
    run(args.keep_running, args.variant, args.schema_mode)
