# Kubernetes Deployment Guide

## Prerequisites
- Kubernetes cluster (1.24+)
- kubectl configured
- 20GB+ storage available

## Quick Start

### 1. Create Namespace
```bash
kubectl apply -f k8s/namespace.yaml
```

### 2. Deploy Database
```bash
# Update secrets first!
kubectl apply -f k8s/postgres.yaml
```

### 3. Deploy Redis
```bash
kubectl apply -f k8s/redis.yaml
```

### 4. Deploy Brain Service
```bash
# Build and push image
docker build -t cypersecurity/brain:latest ./brain
docker push cypersecurity/brain:latest

# Update secrets in k8s/brain.yaml
kubectl apply -f k8s/brain.yaml
```

### 5. Deploy Gateway
```bash
# Build and push image
docker build -t cypersecurity/gateway:latest ./gateway
docker push cypersecurity/gateway:latest

# Update secrets in k8s/gateway.yaml
kubectl apply -f k8s/gateway.yaml
```

### 6. Run Database Migrations
```bash
kubectl exec -n cypersecurity -it statefulset/postgres -- psql -U cyper_admin -d cyper_security -f /path/to/schema.sql
```

## Configuration

### Secrets to Update
1. **postgres-secret**: Database password
2. **brain-secret**: OpenRouter API key, audit signing keys
3. **gateway-secret**: JWT secret, database password

### Scaling
```bash
# View current status
kubectl get hpa -n cypersecurity

# Manual scaling
kubectl scale deployment/gateway --replicas=5 -n cypersecurity
```

## Monitoring
```bash
# View pods
kubectl get pods -n cypersecurity

# View logs
kubectl logs -n cypersecurity deployment/gateway -f

# Port forward for local access
kubectl port-forward -n cypersecurity svc/gateway 8080:8080
```

## Production Checklist
- [ ] Update all secrets with strong random values
- [ ] Configure persistent volume for PostgreSQL
- [ ] Set up Ingress for HTTPS
- [ ] Configure resource limits based on load testing
- [ ] Enable Prometheus metrics
- [ ] Set up log aggregation
- [ ] Configure backup strategy for PostgreSQL
