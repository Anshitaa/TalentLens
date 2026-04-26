#!/usr/bin/env bash
# scripts/minikube-up.sh — deploy TalentLens to minikube
#
# Usage:
#   chmod +x scripts/minikube-up.sh
#   ./scripts/minikube-up.sh
#
# Prerequisites:
#   brew install minikube kubectl helm
#   Docker Desktop must be running before you run this script.

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[talentlens]${NC} $*"; }
warn()  { echo -e "${YELLOW}[warn]${NC} $*"; }

# ── 1. Ensure minikube is running ─────────────────────────────────────────────
info "Checking minikube..."
if ! minikube status 2>/dev/null | grep -q "Running"; then
  info "Starting minikube (4 CPUs, 8 GB RAM)..."
  minikube start --cpus 4 --memory 7500 --driver docker
fi

# ── 2. Enable required addons ─────────────────────────────────────────────────
info "Enabling ingress addon..."
minikube addons enable ingress

# ── 3. Point Docker to minikube's daemon (so images are available in-cluster) ─
info "Switching to minikube Docker daemon..."
eval "$(minikube docker-env)"

# ── 4. Build images inside minikube ───────────────────────────────────────────
info "Building api image..."
docker build -t talentlens/api:latest -f api/Dockerfile .

info "Building frontend image..."
docker build -t talentlens/frontend:latest -f frontend/Dockerfile frontend/

# ── 5. Install KEDA (for Kafka-lag-based HPA) ────────────────────────────────
if ! kubectl get namespace keda &>/dev/null; then
  info "Installing KEDA..."
  helm repo add kedacore https://kedacore.github.io/charts 2>/dev/null || true
  helm repo update
  helm install keda kedacore/keda --namespace keda --create-namespace --wait
else
  info "KEDA already installed, skipping."
fi

# ── 6. Namespace ─────────────────────────────────────────────────────────────
info "Applying namespace..."
kubectl apply -f k8s/namespace.yaml

# ── 7. PostgreSQL (ConfigMap must come before StatefulSet) ───────────────────
info "Applying postgres-init ConfigMap..."
kubectl apply -f k8s/postgres/configmap.yaml

info "Applying postgres..."
kubectl apply -f k8s/postgres/secret.yaml
kubectl apply -f k8s/postgres/pvc.yaml
kubectl apply -f k8s/postgres/statefulset.yaml
kubectl apply -f k8s/postgres/service.yaml

info "Waiting for postgres to be ready..."
kubectl rollout status statefulset/postgres -n talentlens --timeout=120s

# ── 8. Kafka + Zookeeper ─────────────────────────────────────────────────────
info "Applying kafka + zookeeper..."
kubectl apply -f k8s/kafka/zookeeper.yaml
kubectl apply -f k8s/kafka/kafka.yaml

info "Waiting for zookeeper..."
kubectl rollout status statefulset/zookeeper -n talentlens --timeout=60s
info "Waiting for kafka..."
kubectl rollout status statefulset/kafka -n talentlens --timeout=120s

# ── 9. Create Kafka topics ────────────────────────────────────────────────────
info "Running kafka-init Job to create topics..."
kubectl delete job kafka-init -n talentlens --ignore-not-found
kubectl apply -f k8s/kafka/job-init.yaml
info "Waiting for kafka-init Job to complete..."
kubectl wait --for=condition=complete job/kafka-init -n talentlens --timeout=120s

# ── 10. MLflow ───────────────────────────────────────────────────────────────
info "Applying MLflow..."
kubectl apply -f k8s/mlflow/pvc.yaml
kubectl apply -f k8s/mlflow/deployment.yaml
kubectl apply -f k8s/mlflow/service.yaml

# ── 11. API ──────────────────────────────────────────────────────────────────
info "Applying API..."
kubectl apply -f k8s/api/secret-llm.yaml
kubectl apply -f k8s/api/configmap.yaml
kubectl apply -f k8s/api/deployment.yaml
kubectl apply -f k8s/api/service.yaml

info "Waiting for API to be ready..."
kubectl rollout status deployment/api -n talentlens --timeout=180s

# ── 12. Frontend ─────────────────────────────────────────────────────────────
info "Applying frontend..."
kubectl apply -f k8s/frontend/configmap.yaml
kubectl apply -f k8s/frontend/deployment.yaml
kubectl apply -f k8s/frontend/service.yaml

# ── 13. Ingress + KEDA ───────────────────────────────────────────────────────
info "Applying ingress..."
kubectl apply -f k8s/ingress.yaml

info "Applying KEDA ScaledObject..."
kubectl apply -f k8s/keda/scaled-object.yaml

# ── 14. Print access info ─────────────────────────────────────────────────────
MINIKUBE_IP=$(minikube ip)

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
info "TalentLens is up!"
echo ""
echo "  Add to /etc/hosts (run once):"
echo "    echo '${MINIKUBE_IP} talentlens.local' | sudo tee -a /etc/hosts"
echo ""
echo "  Dashboard:  http://talentlens.local"
echo "  API docs:   http://talentlens.local/api/docs"
echo "  MLflow:     http://${MINIKUBE_IP}:30500"
echo ""
echo "  Or use NodePort directly:"
echo "    Frontend → http://${MINIKUBE_IP}:30080"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
