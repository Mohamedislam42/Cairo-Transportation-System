# Cairo Transportation System

Flask + Leaflet web app for transport planning and routing experiments in Greater Cairo.

## Highlights
- Graph routing with `Dijkstra`, `A*`, and time-dependent adaptive paths.
- Emergency routing mode constrained to healthcare facilities (`F9`, `F10`).
- Infrastructure optimization with MST-style network design.
- Dynamic programming modules for bus allocation and maintenance budget planning.
- Greedy optimization for traffic signals and emergency preemption.
- Interactive map UI with route comparison and algorithm race visualization.
- Containerized runtime with Docker for reproducible execution on any machine.

## Tech Stack
- Python, Flask, Gunicorn
- scikit-learn, NumPy, Matplotlib
- Leaflet (map visualization)
- Docker, Docker Compose

## Repository Structure
- `project/app.py` - Flask app and API endpoints
- `project/transport_core.py` - graph model, data, and optimization algorithms
- `project/traffic_predictor.py` - ML congestion prediction logic
- `project/templates/index.html` - main UI
- `project/static/` - frontend assets
- `project/Dockerfile` - production-like app image
- `docker-compose.yml` - local container orchestration
- `render.yaml` - Render deployment blueprint

## Quick Start (Docker - Recommended)
Prerequisites:
- Docker Desktop installed and running
- Docker set to Linux containers mode

From the repository root:

```powershell
docker compose up --build
```

Open:
- `http://localhost:8080`

Useful commands:

```powershell
# Run in background
docker compose up -d --build

# View logs
docker compose logs -f

# Stop and remove containers/network
docker compose down
```

## Local Development (Without Docker)
From the `project` directory:

```powershell
py -3 -m venv .venv
.venv\Scripts\activate
py -3 -m pip install -r requirements.txt
py -3 app.py
```

Open:
- `http://127.0.0.1:5000`

## Main API Endpoints
- `GET /api/health` - health check
- `GET /route` - standard route (`dijkstra` or `astar`)
- `GET /adaptive` - time-dependent route
- `GET /emergency` - emergency route to facilities
- `GET /mst` - infrastructure design result
- `GET /transit` - bus allocation optimization
- `GET /maintenance` - maintenance optimization
- `GET /signal` - signal timing optimization
- `GET /preemption` - emergency preemption plan
- `GET /predict` - traffic prediction

## Deployment
- Docker-based deployment is supported.
- Render blueprint is included in `render.yaml`.

## Course Context
This project was built for CSE112 to demonstrate practical use of:
- Graph algorithms
- Dynamic programming
- Greedy optimization
- Machine learning-assisted traffic estimation

## License

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.
