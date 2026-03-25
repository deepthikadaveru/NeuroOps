#!/usr/bin/env python3
"""
Neuro-Ops CLI
Usage:
  neuro-ops attach <path-to-docker-compose.yml>
  neuro-ops detach
  neuro-ops status
  neuro-ops projects
  neuro-ops switch <project-id>
  neuro-ops version
"""

import sys
import os
import json
import argparse
import requests

API_URL = os.environ.get("NEUROOPS_API_URL", "http://localhost:8000")

BANNER = """
 ███╗   ██╗███████╗██╗   ██╗██████╗  ██████╗        ██████╗ ██████╗ ███████╗
 ████╗  ██║██╔════╝██║   ██║██╔══██╗██╔═══██╗      ██╔═══██╗██╔══██╗██╔════╝
 ██╔██╗ ██║█████╗  ██║   ██║██████╔╝██║   ██║      ██║   ██║██████╔╝███████╗
 ██║╚██╗██║██╔══╝  ██║   ██║██╔══██╗██║   ██║      ██║   ██║██╔═══╝ ╚════██║
 ██║ ╚████║███████╗╚██████╔╝██║  ██║╚██████╔╝      ╚██████╔╝██║     ███████║
 ╚═╝  ╚═══╝╚══════╝ ╚═════╝ ╚═╝  ╚═╝ ╚═════╝        ╚═════╝ ╚═╝     ╚══════╝
 AIOps Intelligence Platform v2.0
"""

VERSION = "2.0.0"


def print_banner():
    print(BANNER)


def cmd_attach(args):
    """Attach Neuro-Ops to an external project."""
    compose_path = os.path.abspath(args.compose_file)
    
    if not os.path.exists(compose_path):
        print(f"[error] File not found: {compose_path}")
        sys.exit(1)

    print(f"[neuro-ops] Scanning {compose_path}...")
    
    try:
        r = requests.post(
            f"{API_URL}/attach",
            json={
                "compose_path": compose_path,
                "project_name": args.name
            },
            timeout=30
        )
        result = r.json()
        
        if r.status_code == 200:
            project = result.get("project", {})
            services = project.get("services", [])
            print(f"\n  ✓ Attached to: {project.get('name', 'unknown')}")
            print(f"  ✓ Services found: {len(services)}")
            for svc in services[:5]:
                name = svc.get('name', '?')
                framework = svc.get('framework', '?')
                port = svc.get('port', '?')
                print(f"    - {name} [{framework}] :{port}")
            if len(services) > 5:
                print(f"    ... and {len(services) - 5} more")
            print(f"\n  Dashboard → http://localhost:3001")
            print(f"  API       → {API_URL}/status\n")
        else:
            print(f"[error] Attach failed: {result.get('error', 'unknown error')}")
            sys.exit(1)
            
    except requests.exceptions.ConnectionError:
        print(f"[error] Cannot reach Neuro-Ops API at {API_URL}")
        print("  Is Neuro-Ops running? Try: docker-compose up -d")
        sys.exit(1)


def cmd_detach(args):
    """Detach from current project, revert to self-demo."""
    try:
        r = requests.post(f"{API_URL}/detach", timeout=10)
        result = r.json()
        print(f"[neuro-ops] {result.get('message', 'Detached successfully')}")
    except requests.exceptions.ConnectionError:
        print(f"[error] Cannot reach Neuro-Ops API at {API_URL}")
        sys.exit(1)


def cmd_status(args):
    """Show current system status."""
    try:
        r = requests.get(f"{API_URL}/status", timeout=10)
        data = r.json()

        project = data.get("project", {})
        anomaly = data.get("anomaly", {}) or {}
        prediction = data.get("prediction", {}) or {}

        health = data.get("health_score", 0)
        health_bar = _health_bar(health)
        risk = prediction.get("risk_level", "unknown")
        risk_icon = {"low": "🟢", "medium": "🟡", "high": "🟠", "critical": "🔴"}.get(risk, "⚪")

        print(f"\n  Project:      {project.get('name', 'unknown')} [{project.get('mode', '?')}]")
        print(f"  Health:       {health_bar} {health}/100")
        print(f"  Risk:         {risk_icon} {risk.upper()}")
        print(f"  Anomaly:      {'⚠ DETECTED' if anomaly.get('is_anomaly') else '✓ Normal'}")
        print(f"  Error Rate:   {data.get('raw_error_rate', 0)*100:.1f}%")
        print(f"  CPU Trend:    {data.get('cpu_trend', '?')}")
        print(f"  Model:        {'trained' if data.get('model_trained') else 'warming up'}")
        print(f"  Updated:      {data.get('timestamp', '?')[:19]}\n")
        
    except requests.exceptions.ConnectionError:
        print(f"[error] Cannot reach Neuro-Ops API at {API_URL}")
        sys.exit(1)


def cmd_projects(args):
    """List all registered projects."""
    try:
        r = requests.get(f"{API_URL}/projects", timeout=10)
        data = r.json()
        projects = data.get("projects", [])
        active_id = data.get("active_project")
        
        print(f"\n  Registered Projects ({len(projects)}):\n")
        for p in projects:
            active_marker = " ← active" if p["id"] == active_id else ""
            mode_icon = "⬡" if p.get("mode") == "self-demo" else "◆"
            print(f"  {mode_icon} {p['id']}{active_marker}")
            print(f"    Name: {p['name']}")
            print(f"    Mode: {p.get('mode', 'unknown')}")
            if p.get("attached_at"):
                print(f"    Attached: {p['attached_at'][:19]}")
            svc_count = len(p.get("services", []))
            print(f"    Services: {svc_count}")
            print()
            
    except requests.exceptions.ConnectionError:
        print(f"[error] Cannot reach Neuro-Ops API at {API_URL}")
        sys.exit(1)


def cmd_switch(args):
    """Switch active project."""
    try:
        r = requests.post(
            f"{API_URL}/projects/switch",
            json={"project_id": args.project_id},
            timeout=10
        )
        result = r.json()
        if r.status_code == 200:
            print(f"[neuro-ops] Switched to project: {args.project_id}")
        else:
            print(f"[error] {result.get('error', 'Switch failed')}")
            sys.exit(1)
    except requests.exceptions.ConnectionError:
        print(f"[error] Cannot reach Neuro-Ops API at {API_URL}")
        sys.exit(1)


def _health_bar(score: float, width: int = 20) -> str:
    filled = int((score / 100) * width)
    bar = "█" * filled + "░" * (width - filled)
    return f"[{bar}]"


def main():
    parser = argparse.ArgumentParser(
        prog="neuro-ops",
        description="Neuro-Ops AIOps Platform"
    )
    parser.add_argument("--version", action="version", version=f"neuro-ops {VERSION}")
    
    subparsers = parser.add_subparsers(dest="command")

    # attach
    attach_parser = subparsers.add_parser("attach", help="Attach to a project")
    attach_parser.add_argument("compose_file", help="Path to docker-compose.yml")
    attach_parser.add_argument("--name", help="Override project name", default=None)
    attach_parser.set_defaults(func=cmd_attach)

    # detach
    detach_parser = subparsers.add_parser("detach", help="Detach from current project")
    detach_parser.set_defaults(func=cmd_detach)

    # status
    status_parser = subparsers.add_parser("status", help="Show system status")
    status_parser.set_defaults(func=cmd_status)

    # projects
    projects_parser = subparsers.add_parser("projects", help="List all projects")
    projects_parser.set_defaults(func=cmd_projects)

    # switch
    switch_parser = subparsers.add_parser("switch", help="Switch active project")
    switch_parser.add_argument("project_id", help="Project ID to switch to")
    switch_parser.set_defaults(func=cmd_switch)

    args = parser.parse_args()

    if not args.command:
        print_banner()
        parser.print_help()
        return

    args.func(args)


if __name__ == "__main__":
    main()