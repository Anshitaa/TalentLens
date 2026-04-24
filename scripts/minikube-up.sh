#!/usr/bin/env bash
# scripts/minikube-up.sh — deploy TalentLens to minikube
#
# Usage:
#   chmod +x scripts/minikube-up.sh
#   ./scripts/minikube-up.sh
#
# Prerequisites:
#   brew install minikube kubectl helm
#   minikube start --cpus 4 --memory 8192

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
if ! minikube status | grep -q "Running"; then
  info "Starting minikube (4 CPUs, 8 GB RAM)..."
  minikube start --cpus 4 --memory 8192 --driver docker
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

# ── 6. Apply manifests ────────────────────────────────────────────────────────
info "Applying namespace..."
kubectl apply -f k8s/namespace.yaml

info "Applying postgres..."
kubectl apply -f k8s/postgres/secret.yaml
kubectl apply -f k8s/postgres/pvc.yaml
kubectl apply -f k8s/postgres/statefulset.yaml
kubectl apply -f k8s/postgres/service.yaml

info "Waiting for postgres to be ready..."
kubectl rollout status statefulset/postgres -n talentlens --timeout=120s

info "Applying kafka + zookeeper..."
kubectl apply -f k8s/kafka/zookeeper.yaml
kubectl apply -f k8s/kafka/kafka.yaml

info "Waiting for zookeeper..."
kubectl rollout status statefulset/zookeeper -n talentlens --timeout=60s
info "Waiting for kafka..."
kubectl rollout status statefulset/kafka -n talentlens --timeout=120s

info "Applying MLflow..."
kubectl apply -f k8s/mlflow/pvc.yaml
kubectl apply -f k8s/mlflow/deployment.yaml
kubectl apply -f k8s/mlflow/service.yaml

info "Applying API..."
kubectl apply -f k8s/api/secret-llm.yaml
kubectl apply -f k8s/api/configmap.yaml
kubectl apply -f k8s/api/deployment.yaml
kubectl apply -f k8s/api/service.yaml

info "Waiting for API to be ready..."
kubectl rollout status deployment/api -n talentlens --timeout=180s

info "Applying frontend..."
kubectl apply -f k8s/frontend/configmap.yaml
kubectl apply -f k8s/frontend/deployment.yaml
kubectl apply -f k8s/frontend/service.yaml

info "Applying ingress..."
kubectl apply -f k8s/ingress.yaml

info "Applying KEDA ScaledObject..."
kubectl apply -f k8s/keda/scaled-object.yaml

# ── 7. Print access info ──────────────────────────────────────────────────────
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
