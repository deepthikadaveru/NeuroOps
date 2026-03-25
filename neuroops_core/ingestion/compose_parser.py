"""
Docker Compose Parser
Reads any docker-compose.yml and extracts service info,
ports, environment variables, and health check endpoints.
Auto-detects service types (Flask, Express, Django, Spring, etc.)
"""

import yaml
import re
from typing import Optional

# Known framework signatures — detect from image name or env vars
FRAMEWORK_SIGNATURES = {
    "flask": ["flask", "python", "gunicorn", "uvicorn", "fastapi"],
    "express": ["node", "express", "nodejs"],
    "django": ["django"],
    "spring": ["spring", "java", "openjdk"],
    "rails": ["ruby", "rails"],
    "laravel": ["php", "laravel"],
    "go": ["golang", "go:"],
    "dotnet": ["dotnet", "aspnet", "microsoft/dotnet"],
    "nginx": ["nginx"],
    "postgres": ["postgres"],
    "mysql": ["mysql", "mariadb"],
    "redis": ["redis"],
    "mongodb": ["mongo"],
    "kafka": ["kafka", "confluent"],
    "rabbitmq": ["rabbitmq"],
}

# Default metrics/health paths per framework
FRAMEWORK_DEFAULTS = {
    "flask":    {"metrics": "/metrics", "health": "/health"},
    "fastapi":  {"metrics": "/metrics", "health": "/health"},
    "express":  {"metrics": "/metrics", "health": "/health"},
    "django":   {"metrics": "/metrics", "health": "/health"},
    "spring":   {"metrics": "/actuator/prometheus", "health": "/actuator/health"},
    "rails":    {"metrics": "/metrics", "health": "/health"},
    "go":       {"metrics": "/metrics", "health": "/health"},
    "dotnet":   {"metrics": "/metrics", "health": "/health"},
    "nginx":    {"metrics": None, "health": None},
    "postgres": {"metrics": None, "health": None},
    "mysql":    {"metrics": None, "health": None},
    "redis":    {"metrics": None, "health": None},
    "mongodb":  {"metrics": None, "health": None},
    "kafka":    {"metrics": None, "health": None},
    "rabbitmq": {"metrics": None, "health": None},
}

# Infrastructure services — monitor differently, don't scrape metrics from these
INFRA_SERVICES = {"postgres", "mysql", "redis", "mongodb", "kafka", "rabbitmq", "nginx"}


def detect_framework(service_config: dict) -> str:
    """Detect framework from image name, build context, or environment variables."""
    image = service_config.get("image", "").lower()
    build = str(service_config.get("build", "")).lower()
    environment = service_config.get("environment", {})
    
    if isinstance(environment, list):
        env_str = " ".join(environment).lower()
    else:
        env_str = " ".join(str(v) for v in environment.values()).lower()

    search_text = f"{image} {build} {env_str}"

    for framework, signatures in FRAMEWORK_SIGNATURES.items():
        for sig in signatures:
            if sig in search_text:
                return framework

    return "unknown"


def extract_port(service_config: dict) -> Optional[int]:
    """Extract the primary exposed port from a service."""
    ports = service_config.get("ports", [])
    if not ports:
        # Check expose field
        expose = service_config.get("expose", [])
        if expose:
            try:
                return int(str(expose[0]).split("/")[0])
            except:
                pass
        return None

    # ports can be "HOST:CONTAINER" or just "PORT"
    first_port = str(ports[0])
    if ":" in first_port:
        # Take the container port (right side)
        container_port = first_port.split(":")[-1]
    else:
        container_port = first_port

    # Remove protocol suffix like /tcp
    container_port = container_port.split("/")[0]

    try:
        return int(container_port)
    except:
        return None


def extract_host_port(service_config: dict) -> Optional[int]:
    """Extract the host-side port (for external access)."""
    ports = service_config.get("ports", [])
    if not ports:
        return None
    
    first_port = str(ports[0])
    if ":" in first_port:
        host_port = first_port.split(":")[0]
        # Remove any bind address like 0.0.0.0:
        if "." in host_port:
            host_port = host_port.split(".")[-1]
        try:
            return int(host_port)
        except:
            return None
    return None


def is_infra_service(framework: str, service_name: str) -> bool:
    """Determine if this is an infrastructure service (DB, cache, queue)."""
    return framework in INFRA_SERVICES or any(
        infra in service_name.lower() for infra in INFRA_SERVICES
    )


def parse_compose(compose_path: str) -> dict:
    """
    Parse a docker-compose.yml and return structured service info.
    
    Returns:
        {
            "project_id": str,
            "project_name": str,
            "services": [...],
            "infra_services": [...],
            "networks": [...],
            "raw_services": int
        }
    """
    with open(compose_path) as f:
        compose = yaml.safe_load(f)

    services_config = compose.get("services", {})
    project_name = compose.get("name", compose_path.split("/")[-2] if "/" in compose_path else "project")
    project_id = re.sub(r"[^a-z0-9-]", "-", project_name.lower())

    app_services = []
    infra_services = []

    for service_name, service_config in services_config.items():
        if service_config is None:
            service_config = {}

        framework = detect_framework(service_config)
        port = extract_port(service_config)
        host_port = extract_host_port(service_config)
        defaults = FRAMEWORK_DEFAULTS.get(framework, {"metrics": "/metrics", "health": "/health"})

        service_info = {
            "name": service_name,
            "host": service_name,  # Docker DNS — service name is the hostname
            "port": port,
            "host_port": host_port,
            "framework": framework,
            "metrics_path": defaults["metrics"],
            "health_path": defaults["health"],
            "image": service_config.get("image", "custom build"),
            "is_infra": is_infra_service(framework, service_name),
            "depends_on": list(service_config.get("depends_on", {}).keys()) 
                         if isinstance(service_config.get("depends_on"), dict)
                         else service_config.get("depends_on", []),
        }

        if service_info["is_infra"]:
            infra_services.append(service_info)
        else:
            app_services.append(service_info)

    return {
        "project_id": project_id,
        "project_name": project_name,
        "compose_path": compose_path,
        "services": app_services,
        "infra_services": infra_services,
        "total_services": len(services_config),
        "networks": list(compose.get("networks", {}).keys()),
    }


def generate_prometheus_config(parsed: dict, existing_jobs: list = None) -> str:
    """
    Generate a Prometheus scrape config for all discovered services.
    Merges with existing jobs to avoid overwriting Neuro-Ops own targets.
    """
    jobs = existing_jobs or [
        # Keep Neuro-Ops own services always
        {"job": "neuroops-web",          "target": "web:5000"},
        {"job": "neuroops-api",          "target": "api:5001"},
        {"job": "cadvisor",              "target": "cadvisor:8080"},
        {"job": "node-exporter",         "target": "node-exporter:9100"},
    ]

    # Add jobs for newly discovered services
    for svc in parsed["services"]:
        if svc["port"] and svc["metrics_path"]:
            job_name = f"{parsed['project_id']}-{svc['name']}"
            target = f"{svc['host']}:{svc['port']}"
            # Avoid duplicates
            if not any(j["target"] == target for j in jobs):
                jobs.append({"job": job_name, "target": target, "metrics_path": svc["metrics_path"]})

    lines = [
        "global:",
        "  scrape_interval: 5s",
        "  evaluation_interval: 5s",
        "",
        "scrape_configs:",
    ]

    for job in jobs:
        lines.append(f"  - job_name: '{job['job']}'")
        if job.get("metrics_path") and job["metrics_path"] != "/metrics":
            lines.append(f"    metrics_path: '{job['metrics_path']}'")
        lines.append("    static_configs:")
        lines.append(f"      - targets: ['{job['target']}']")
        lines.append("")

    return "\n".join(lines)


def print_summary(parsed: dict):
    """Print a human-readable summary of what was discovered."""
    print(f"\n{'='*50}")
    print(f"  PROJECT: {parsed['project_name']}")
    print(f"  ID:      {parsed['project_id']}")
    print(f"{'='*50}")
    print(f"\n  App Services ({len(parsed['services'])}):")
    for svc in parsed["services"]:
        port_str = f":{svc['port']}" if svc["port"] else ":?"
        print(f"    ✓ {svc['name']}{port_str}  [{svc['framework']}]")
        if svc["metrics_path"]:
            print(f"      metrics → {svc['metrics_path']}")
        if svc["health_path"]:
            print(f"      health  → {svc['health_path']}")

    if parsed["infra_services"]:
        print(f"\n  Infrastructure ({len(parsed['infra_services'])}):")
        for svc in parsed["infra_services"]:
            print(f"    ⬡ {svc['name']}  [{svc['framework']}]")

    print(f"\n  Networks: {parsed['networks'] or ['default']}")
    print(f"{'='*50}\n")