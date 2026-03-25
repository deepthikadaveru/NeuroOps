from .compose_parser import parse_compose, generate_prometheus_config, print_summary
from .registry import (
    register_project, get_active_project, get_project,
    list_projects, set_active_project, remove_project, get_active_services
)
from .attacher import attach, detach