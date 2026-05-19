# Neuro-Ops

### Autonomous AIOps Platform for Real-Time Anomaly Detection, Root Cause Analysis, and Self-Healing in Microservice Architectures

---

## Overview

Neuro-Ops is an AI-driven AIOps platform designed to monitor distributed microservice systems, detect anomalies in real time, analyze root causes, and automate recovery actions.

The platform combines monitoring, machine learning, intelligent diagnostics, and automation to reduce downtime and improve system reliability in modern cloud-native infrastructures.

---

## Features

- Real-time system monitoring
- AI-based anomaly detection
- Root cause analysis engine
- Self-healing automation
- Interactive monitoring dashboard
- API-driven architecture
- Dockerized deployment
- Payment integration support

---

## Tech Stack

### Backend
- Python
- Flask / FastAPI
- REST APIs

### Frontend
- HTML
- CSS
- JavaScript

### Monitoring & Visualization
- Prometheus
- Grafana

### DevOps
- Docker
- Docker Compose

### Machine Learning
- Scikit-learn
- NumPy
- Pandas

---

## Project Structure

```bash
Neuro-Ops/
│
├── dashboard/              # Monitoring dashboard
├── monitoring/             # Monitoring configurations
├── neuroops_core/          # Core anomaly detection & RCA engine
├── services/
│   ├── api/                # Backend APIs
│   └── web/                # Frontend application
│
├── docker-compose.yml
├── demo.py
├── setup.py
└── README.md
```

---

## Core Modules

### Anomaly Detection
Detects unusual behavior in system metrics such as:
- CPU spikes
- Memory overuse
- Latency increases
- Service failures

### Root Cause Analysis
Analyzes logs and telemetry data to identify the probable source of failures.

### Self-Healing Engine
Automatically performs corrective actions such as:
- Restarting failed services
- Triggering alerts
- Recovering unhealthy components

---

## Installation

### Clone the Repository

```bash
git clone https://github.com/deepthikadaveru/neuro-ops.git
cd neuro-ops
```

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Run the Application

```bash
python demo.py
```

---

## Docker Setup

```bash
docker-compose up --build
```

---

## Screenshots

Neuro-Ops Dashboard – Normal Operation
<img width="1015" height="536" alt="image" src="https://github.com/user-attachments/assets/6618a935-ceb6-4bb0-86b6-3f6002573a9c" />

Neuro-Ops Dashboard – Anomaly Detected (Predicted Failure, Critical)
<img width="978" height="518" alt="image" src="https://github.com/user-attachments/assets/3f6999e3-c845-4099-8594-ed3fc67e8590" />

NovaPay Payment Gateway – Successful Transaction
<img width="676" height="617" alt="image" src="https://github.com/user-attachments/assets/e4d112de-6288-4362-b425-a59d5d19b610" />

NovaPay Payment Gateway – Payment Failure with Neuro-Ops Responding
<img width="697" height="633" alt="image" src="https://github.com/user-attachments/assets/8567a67d-508d-4e13-8e85-5eaceaa615ce" />

---

## Future Enhancements

- Predictive failure analysis
- Kubernetes integration
- Advanced ML anomaly models
- Multi-cloud infrastructure support
- Automated incident reporting

---

## Use Cases

- Cloud infrastructure monitoring
- Enterprise DevOps environments
- Microservice health management
- Automated IT operations

---

## License

This project is licensed under the MIT License.

---

## Author

**Deepthi Kadaveru**  
B.Tech CSE Student  
AI • DevOps • Full Stack • Machine Learning
