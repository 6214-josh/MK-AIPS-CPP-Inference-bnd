#!/usr/bin/env bash
set -euo pipefail

echo "== Copy changed files into project =="
cp /home/josh/mk-apis-patch/backend/app/main.py /home/josh/mk-apis/MK-AIPS-CPP-Inference-bnd-main/app/main.py
cp /home/josh/mk-apis-patch/backend/requirements.txt /home/josh/mk-apis/MK-AIPS-CPP-Inference-bnd-main/requirements.txt
cp /home/josh/mk-apis-patch/backend/Dockerfile /home/josh/mk-apis/MK-AIPS-CPP-Inference-bnd-main/Dockerfile
cp /home/josh/mk-apis-patch/backend/.dockerignore /home/josh/mk-apis/MK-AIPS-CPP-Inference-bnd-main/.dockerignore

cp /home/josh/mk-apis-patch/frontend/src/style.css /home/josh/mk-apis/MK-AIPS-CPP-Inference-fnd-main/src/style.css
cp /home/josh/mk-apis-patch/frontend/Dockerfile /home/josh/mk-apis/MK-AIPS-CPP-Inference-fnd-main/Dockerfile
cp /home/josh/mk-apis-patch/frontend/nginx.conf /home/josh/mk-apis/MK-AIPS-CPP-Inference-fnd-main/nginx.conf
cp /home/josh/mk-apis-patch/frontend/.dockerignore /home/josh/mk-apis/MK-AIPS-CPP-Inference-fnd-main/.dockerignore

mkdir -p /home/josh/mk-apis/k8s
cp /home/josh/mk-apis-patch/k8s/*.yaml /home/josh/mk-apis/k8s/
cp /home/josh/mk-apis-patch/k8s/*.sh /home/josh/mk-apis/k8s/
chmod +x /home/josh/mk-apis/k8s/*.sh

echo "== Docker login Harbor =="
docker login 192.168.1.113:30002

echo "== Build and push backend:v2 =="
cd /home/josh/mk-apis/MK-AIPS-CPP-Inference-bnd-main
docker build -t 192.168.1.113:30002/mk-apis/backend:v2 .
docker push 192.168.1.113:30002/mk-apis/backend:v2

echo "== Build and push frontend:v2 =="
cd /home/josh/mk-apis/MK-AIPS-CPP-Inference-fnd-main
docker build --build-arg VITE_AIPS_API_BASE_URL=http://192.168.1.113:30089/api -t 192.168.1.113:30002/mk-apis/frontend:v2 .
docker push 192.168.1.113:30002/mk-apis/frontend:v2

echo "== Apply K8s and Monitoring =="
/home/josh/mk-apis/k8s/apply-aips-monitoring.sh
