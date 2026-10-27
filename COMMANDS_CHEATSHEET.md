# Student Attendance Management System — DevOps Commands Cheat Sheet 📜

> **Project Directory:** `C:\Users\Yash\OneDrive\Desktop\devops project`  
> **Environment:** Windows PowerShell  

---

## 📌 Section 1: Preparation & Local Application (FA1)

```powershell
# 1. Navigate to project root directory
cd "C:\Users\Yash\OneDrive\Desktop\devops project"

# 2. Activate virtual environment
.\.venv\Scripts\Activate.ps1

# 3. Run all 9 automated Pytest unit & integration tests
pytest -v

# 4. Run the Flask web application locally
python -m app.app
```
> **Stop local server:** Press `Ctrl + C` in PowerShell.

---

## 📌 Section 2: Docker Containerization (FA2)

```powershell
# 1. Build the Docker image
docker build -t student-attendance:v1 .

# 2. Run the application as a detached container with persistent storage
docker run -d --name student-attendance-app -p 5000:5000 -v attendance-data:/app/data student-attendance:v1

# 3. Verify container status and health check probe
docker ps

# 4. View container logs
docker logs student-attendance-app

# 5. Stop and remove the test container (frees port 5000 for Kubernetes)
docker rm -f student-attendance-app
```

---

## 📌 Section 3: Kubernetes Orchestration (FA2)

```powershell
# 1. Verify Kubernetes cluster status
kubectl get nodes

# 2. Apply all Kubernetes manifests (Storage, Deployment, Service)
kubectl apply -f k8s/pvc.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml

# 3. Verify Pod status (1/1 Running), PVC (Bound), and Service (NodePort)
kubectl get pods,pvc,svc

# 4. Check live Pod logs (verifies health checks hitting /healthz)
kubectl logs -l app=student-attendance

# 5. Forward port 5000 from Kubernetes to your browser
kubectl port-forward svc/student-attendance-service 5000:5000
```
> **Stop port-forwarding:** Press `Ctrl + C` in PowerShell.

---

## 📌 Section 4: Monitoring with Prometheus & Grafana (FA2)

```powershell
# 1. Start Prometheus and Grafana monitoring stack in background
docker compose -f monitoring/docker-compose.monitoring.yml up -d

# 2. Check running monitoring containers
docker ps --filter "name=attendance-"

# 3. Stop monitoring stack when demo is finished
docker compose -f monitoring/docker-compose.monitoring.yml down
```

---

## 📌 Section 5: Git & GitHub Actions CI

```powershell
# 1. Check local Git status
git status

# 2. View commit history
git log --oneline

# 3. Push any new changes to GitHub (triggers GitHub Actions CI automatically)
git push origin main
```

---

## 🌐 Quick Reference: All Demonstration URLs

| Service | Local URL | What to Show the Examiner |
| :--- | :--- | :--- |
| **Attendance Web App** | http://localhost:5000 | Add students, mark attendance, view history |
| **App Health Check** | http://localhost:5000/healthz | JSON response: `{"status": "healthy"}` |
| **Prometheus Raw Metrics** | http://localhost:5000/metrics | OpenMetrics formatted data for SRE scraping |
| **Prometheus UI** | http://localhost:9090 | Check **Status > Targets** (`UP`), query metrics |
| **Grafana Dashboard** | http://localhost:3000 | Login: `admin`/`admin`, view throughput & latency |
| **GitHub Actions (CI)** | https://github.com/yashsonje/student-attendance-devops/actions | Automated Pytest run with green checkmark |

---

## 🧹 One-Command Clean Up (After Presentation)

```powershell
# Stop Kubernetes port-forward (Ctrl + C in that window)
# Remove Kubernetes resources:
kubectl delete -f k8s/service.yaml -f k8s/deployment.yaml -f k8s/pvc.yaml

# Stop Monitoring stack:
docker compose -f monitoring/docker-compose.monitoring.yml down
```
