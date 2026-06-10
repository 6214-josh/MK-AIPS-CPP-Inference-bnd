#!/usr/bin/env bash
set -euo pipefail

echo "== Apply AIPS backend/frontend deployments =="
kubectl apply -f /home/josh/mk-apis/k8s/backend.yaml
kubectl apply -f /home/josh/mk-apis/k8s/frontend.yaml

echo "== Apply Prometheus ServiceMonitors and postgres exporter =="
kubectl apply -f /home/josh/mk-apis/k8s/aips-backend-servicemonitor.yaml
kubectl apply -f /home/josh/mk-apis/k8s/aips-frontend-servicemonitor.yaml
kubectl apply -f /home/josh/mk-apis/k8s/postgres-exporter.yaml

echo "== Apply Grafana dashboard ConfigMap =="
kubectl apply -f /home/josh/mk-apis/k8s/aips-grafana-dashboard.yaml

echo "== Restart deployments =="
kubectl rollout restart deployment/aips-backend
kubectl rollout restart deployment/aips-frontend

echo "== Status =="
kubectl get pods -o wide
kubectl get servicemonitor -A | grep -E 'aips|NAME' || true
kubectl get pods -n cattle-monitoring-system -o wide
