"""
Attach Engine
The brain behind `neuro-ops attach`.
Given a docker-compose.yml it:
1. Parses and discovers all services
2. Generates Prometheus scrape config
3. Injects OpenTelemetry collector as a sidecar
4. Registers the project in the registry
5. Hot-reloads Prometheus without restart
"""

import os
import json
import requests
import shutil
from datetime import datetime
from .compose_parser import parse_compose, generate_prometheus_config, print_summary
from .registry import register_project, set_active_project

PROMETHEUS_CONFIG_PATH = os.environ.get("PROMETHEUS_CONFIG_PATH", "/etc/prometheus/prometheus.yml")
PROMETHEUS_URL = os.environ.get("PROMETHEUS_URL", "http://prometheus:9090")
REGISTRY_DATA_PATH = "/data/neuro-ops"


def reload_prometheus() -> bool:
    """Send reload signal to Prometheus via its HTTP API."""
    try:
        r = requests.post(f"{PROMETHEUS_URL}/-/reload", timeout=5)
        if r.status_code == 200:
            print("[attach] Prometheus config reloaded successfully")
            return True
        else:
            print(f"[attach] Prometheus reload returned {r.status_code}")
            return False
    except Exception as e:
        print(f"[attach] Could not reload Prometheus: {e}")
        return False


def backup_prometheus_config() -> str:
    """Backup current Prometheus config before modifying."""
    backup_path = f"{PROMETHEUS_CONFIG_PATH}.backup.{int(datetime.utcnow().timestamp())}"
    if os.path.exists(PROMETHEUS_CONFIG_PATH):
        shutil.copy2(PROMETHEUS_CONFIG_PATH, backup_path)
        print(f"[attach] backed up prometheus config to {backup_path}")
    return backup_path


def write_prometheus_config(config_str: str):
    """Write new Prometheus config to disk."""
    os.makedirs(os.path.dirname(PROMETHEUS_CONFIG_PATH), exist_ok=True)
    with open(PROMETHEUS_CONFIG_PATH, "w") as f:
        f.write(config_str)
    print(f"[attach] wrote prometheus config ({len(config_str.splitlines())} lines)")


def generate_otel_config(parsed: dict) -> str:
    """
    Generate OpenTelemetry Collector config for the attached project.
    Collects logs and traces from all discovered services.
    """
    service_names = [s["name"] for s in parsed["services"]]
    
    config = {
        "receivers": {
            "otlp": {
                "protocols": {
                    "grpc": {"endpoint": "0.0.0.0:4317"},
                    "http": {"endpoint": "0.0.0.0:4318"}
                }
            },
            "filelog": {
                "include": [f"/var/log/containers/{name}*.log" for name in service_names],
                "operators": [
                    {"type": "json_parser", "if": "body matches '\\{.*\\}'"},
                    {"type": "move", "from": "attributes.log", "to": "body", "if": "attributes.log != nil"}
                ]
            }
        },
        "processors": {
            "batch": {},
            "resource": {
                "attributes": [
                    {"action": "insert", "key": "neuroops.project", "value": parsed["project_id"]}
                ]
            }
        },
        "exporters": {
            "loki": {
                "endpoint": "http://loki:3100/loki/api/v1/push",
                "labels": {
                    "resource": {
                        "service.name": "service_name",
                        "neuroops.project": "project"
                    }
                }
            },
            "otlp/tempo": {
                "endpoint": "tempo:4317",
                "tls": {"insecure": True}
            }
        },
        "service": {
            "pipelines": {
                "logs": {
                    "receivers": ["otlp", "filelog"],
                    "processors": ["batch", "resource"],
                    "exporters": ["loki"]
                },
                "traces": {
                    "receivers": ["otlp"],
                    "processors": ["batch", "resource"],
                    "exporters": ["otlp/tempo"]
                }
            }
        }
    }
    
    import yaml
    return yaml.dump(config, default_flow_style=False)


def save_project_config(parsed: dict, prometheus_config: str, otel_config: str):
    """Save all generated configs for this project."""
    project_dir = f"{REGISTRY_DATA_PATH}/projects/{parsed['project_id']}"
    os.makedirs(project_dir, exist_ok=True)
    
    with open(f"{project_dir}/prometheus.yml", "w") as f:
        f.write(prometheus_config)
    
    with open(f"{project_dir}/otel-collector.yml", "w") as f:
        f.write(otel_config)
    
    with open(f"{project_dir}/parsed.json", "w") as f:
        json.dump(parsed, f, indent=2)
    
    print(f"[attach] saved project configs to {project_dir}")


def attach(compose_path: str, project_name: str = None) -> dict:
    """
    Main attach function. Call this with a path to docker-compose.yml.
    
    Returns the registered project dict.
    """
    print(f"\n[neuro-ops] Attaching to project: {compose_path}")
    
    # 1. Parse the compose file
    if not os.path.exists(compose_path):
        raise FileNotFoundError(f"Compose file not found: {compose_path}")
    
    parsed = parse_compose(compose_path)
    
    if project_name:
        parsed["project_name"] = project_name
        import re
        parsed["project_id"] = re.sub(r"[^a-z0-9-]", "-", project_name.lower())
    
    # 2. Print discovery summary
    print_summary(parsed)
    
    # 3. Generate Prometheus config
    prometheus_config = generate_prometheus_config(parsed)
    
    # 4. Generate OTel collector config
    otel_config = generate_otel_config(parsed)
    
    # 5. Save configs to disk
    save_project_config(parsed, prometheus_config, otel_config)
    
    # 6. Write and reload Prometheus
    backup_prometheus_config()
    write_prometheus_config(prometheus_config)
    reloaded = reload_prometheus()
    
    # 7. Register in project registry
    project = register_project(
        project_id=parsed["project_id"],
        name=parsed["project_name"],
        compose_path=compose_path,
        services=parsed["services"] + parsed["infra_services"]
    )
    
    print(f"\n[neuro-ops] ✓ Project '{parsed['project_name']}' attached successfully")
    print(f"[neuro-ops] ✓ Monitoring {len(parsed['services'])} app services")
    print(f"[neuro-ops] ✓ Prometheus {'reloaded' if reloaded else 'config updated (manual reload needed)'}")
    print(f"[neuro-ops] ✓ Dashboard: http://localhost:3001")
    print(f"[neuro-ops] ✓ API: http://localhost:8000/status\n")
    
    return project


def detach(project_id: str = None) -> bool:
    """
    Detach a project and revert to self-demo mode.
    """
    from .registry import set_active_project, get_active_project
    
    if project_id is None:
        project_id = get_active_project()["id"]
    
    if project_id == "self-demo":
        print("[attach] already in self-demo mode")
        return True
    
    # Revert to self-demo prometheus config
    self_demo_config = generate_prometheus_config({"project_id": "self-demo", "services": []})
    write_prometheus_config(self_demo_config)
    reload_prometheus()
    set_active_project("self-demo")
    
    print(f"[neuro-ops] detached from {project_id}, reverted to self-demo mode")
    return True