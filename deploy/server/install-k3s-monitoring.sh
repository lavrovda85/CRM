#!/usr/bin/env bash
# Install k3s (single-node) + Helm + kube-prometheus-stack (Grafana).
# Does NOT bind port 80 — safe alongside Docker Compose CRM on :80.
# Grafana: NodePort 30080, Prometheus: 30090, k3s API: 6443
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run with: sudo bash $0"
  exit 1
fi

curl -sfL https://get.k3s.io | INSTALL_K3S_EXEC="server --disable traefik" sh -
mkdir -p /root/.kube
cp /etc/rancher/k3s/k3s.yaml /root/.kube/config
chmod 600 /etc/rancher/k3s/k3s.yaml

export KUBECONFIG=/etc/rancher/k3s/k3s.yaml

curl -sfL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash

helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

kubectl create namespace monitoring --dry-run=client -o yaml | kubectl apply -f -

GRAFANA_PASS="${GRAFANA_ADMIN_PASSWORD:-ChangeMeGrafana!}"

helm upgrade --install kube-prom prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --set grafana.service.type=NodePort \
  --set grafana.service.nodePort=30080 \
  --set grafana.adminPassword="${GRAFANA_PASS}" \
  --set prometheus.service.type=NodePort \
  --set prometheus.service.nodePort=30090 \
  --wait --timeout 15m

echo "k3s + monitoring OK."
echo "Grafana:    http://SERVER_IP:30080  (user: admin — set GRAFANA_ADMIN_PASSWORD env before running this script)"
echo "Prometheus: http://SERVER_IP:30090"
echo "Kube API:   https://SERVER_IP:6443"
