"""
Project Registry
Stores and manages all projects attached to Neuro-Ops.
Persists to disk so projects survive container restarts.
"""

import json
import os
from datetime import datetime
from typing import Optional

REGISTRY_PATH = "/data/neuro-ops/registry.json"

DEFAULT_PROJECT = {
    "id": "self-demo",
    "name": "Neuro-Ops Self Demo",
    "description": "Built-in demo project — Neuro-Ops monitoring itself",
    "compose_path": None,
    "services": [
        {
            "name": "web",
            "host": "web",
            "port": 5000,
            "metrics_path": "/metrics",
            "health_path": "/health",
            "type": "flask"
        },
        {
            "name": "api",
            "host": "api",
            "port": 5001,
            "metrics_path": "/metrics",
            "health_path": "/health",
            "type": "flask"
        }
    ],
    "attached_at": None,
    "status": "active",
    "mode": "self-demo"
}


def _load() -> dict:
    os.makedirs(os.path.dirname(REGISTRY_PATH), exist_ok=True)
    if not os.path.exists(REGISTRY_PATH):
        # first run — seed with self-demo project
        data = {
            "active_project": "self-demo",
            "projects": {"self-demo": DEFAULT_PROJECT}
        }
        _save(data)
        return data
    with open(REGISTRY_PATH) as f:
        return json.load(f)


def _save(data: dict):
    os.makedirs(os.path.dirname(REGISTRY_PATH), exist_ok=True)
    with open(REGISTRY_PATH, "w") as f:
        json.dump(data, f, indent=2)


def register_project(project_id: str, name: str, compose_path: str, services: list) -> dict:
    data = _load()
    project = {
        "id": project_id,
        "name": name,
        "description": f"Attached from {compose_path}",
        "compose_path": compose_path,
        "services": services,
        "attached_at": datetime.utcnow().isoformat(),
        "status": "active",
        "mode": "attached"
    }
    data["projects"][project_id] = project
    data["active_project"] = project_id
    _save(data)
    print(f"[registry] registered project: {project_id} with {len(services)} services")
    return project


def get_active_project() -> dict:
    data = _load()
    active_id = data.get("active_project", "self-demo")
    return data["projects"].get(active_id, DEFAULT_PROJECT)


def get_project(project_id: str) -> Optional[dict]:
    data = _load()
    return data["projects"].get(project_id)


def list_projects() -> list:
    data = _load()
    return list(data["projects"].values())


def set_active_project(project_id: str) -> bool:
    data = _load()
    if project_id not in data["projects"]:
        return False
    data["active_project"] = project_id
    _save(data)
    print(f"[registry] active project set to: {project_id}")
    return True


def remove_project(project_id: str) -> bool:
    if project_id == "self-demo":
        print("[registry] cannot remove self-demo project")
        return False
    data = _load()
    if project_id not in data["projects"]:
        return False
    del data["projects"][project_id]
    if data["active_project"] == project_id:
        data["active_project"] = "self-demo"
    _save(data)
    return True


def get_active_services() -> list:
    project = get_active_project()
    return project.get("services", [])