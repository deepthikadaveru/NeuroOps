"""
Neuro-Ops Core API
All endpoints for the dashboard and CLI.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import threading

from pipeline import feature_log, anomaly_log, detector, predictor
from automator import get_action_log
from ingestion import (
    attach, detach,
    get_active_project, list_projects, set_active_project
)

app = FastAPI(title="Neuro-Ops Core API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Status ───────────────────────────────────────────────────────────────────

@app.get("/status")
def status():
    project = get_active_project()
    if not feature_log:
        return {
            "status": "warming up",
            "project": project
        }
    latest = feature_log[-1]
    return {
        "status": "running",
        "project": {
            "id": project["id"],
            "name": project["name"],
            "mode": project.get("mode", "self-demo"),
            "services": len(project.get("services", []))
        },
        "health_score": latest["health_score"],
        "cpu_trend": latest["cpu_trend"],
        "error_trend": latest["error_trend"],
        "latency_trend": latest["latency_trend"],
        "raw_error_rate": latest["raw_error_rate"],
        "anomaly": latest.get("anomaly"),
        "root_cause": latest.get("root_cause"),
        "prediction": latest.get("prediction"),
        "auto_action": latest.get("auto_action"),
        "timestamp": latest["timestamp"],
        "model_trained": detector.is_trained
    }


# ─── Project Management ───────────────────────────────────────────────────────

class AttachRequest(BaseModel):
    compose_path: str
    project_name: Optional[str] = None


class SwitchRequest(BaseModel):
    project_id: str


@app.post("/attach")
def attach_project(req: AttachRequest):
    """Attach Neuro-Ops to an external project via docker-compose.yml."""
    try:
        project = attach(
            compose_path=req.compose_path,
            project_name=req.project_name
        )
        return {
            "success": True,
            "project": project,
            "message": f"Attached to {project['name']} successfully"
        }
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/detach")
def detach_project():
    """Detach from current project, revert to self-demo mode."""
    project = get_active_project()
    project_id = project["id"]
    detach(project_id)
    return {
        "success": True,
        "message": f"Detached from {project_id}, reverted to self-demo mode"
    }


@app.get("/projects")
def projects():
    """List all registered projects."""
    all_projects = list_projects()
    active = get_active_project()
    return {
        "active_project": active["id"],
        "projects": all_projects
    }


@app.post("/projects/switch")
def switch_project(req: SwitchRequest):
    """Switch active project."""
    success = set_active_project(req.project_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Project not found: {req.project_id}")
    return {
        "success": True,
        "active_project": req.project_id
    }


@app.get("/projects/{project_id}")
def get_project_detail(project_id: str):
    """Get details for a specific project."""
    from neuroops_core.ingestion import get_project
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project not found: {project_id}")
    return project


# ─── Intelligence ─────────────────────────────────────────────────────────────

@app.get("/prediction")
def prediction():
    return predictor.predict()


@app.get("/prediction/history")
def prediction_history():
    return {"data": predictor.get_history()}


@app.get("/anomalies")
def anomalies():
    return {
        "total": len(anomaly_log),
        "recent": anomaly_log[-10:]
    }


@app.get("/actions")
def actions():
    log = get_action_log()
    return {
        "total": len(log),
        "recent": log[-10:]
    }


@app.get("/features/latest")
def latest_features():
    if not feature_log:
        return {"error": "no data yet"}
    return feature_log[-1]


@app.get("/features/history")
def feature_history():
    return {"count": len(feature_log), "data": feature_log[-20:]}


# ─── Health ───────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "version": "2.0.0"}


@app.get("/")
def root():
    return {
        "name": "Neuro-Ops API",
        "version": "2.0.0",
        "docs": "/docs",
        "status": "/status"
    }