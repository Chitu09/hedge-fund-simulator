# DevOps setup — Multi-Strategy Hedge Fund Simulator

This repo already includes the app, the end-date fix and Prometheus metrics wired into `app.py`.
Replace `chitu09` in `k8s/deployment.yaml` and `terraform/variables.tf` with the account that owns this repo.

```
.github/workflows/ci-cd.yml   GitHub Actions: lint → test → build → push → deploy
Dockerfile, .dockerignore     container image
docker-compose.yml            local app + Prometheus + Grafana
k8s/                          namespace, deployment, service, HPA
terraform/                    Azure resource group + AKS (or App Service)
monitoring/                   Prometheus scrape config, Grafana datasource + dashboard
metrics.py                    Prometheus metrics for Streamlit (port 8000)
tests/test_analytics.py       offline unit tests (synthetic data, no Yahoo calls)
requirements*.txt             runtime + dev dependencies
```

---

## 1. Versioning

```bash
git tag -a v1.0.0 -m "First tagged release"
git push origin v1.0.0          # CI builds image tag 1.0.0
```

On GitHub: **Settings → Branches → Add rule for `main`** → require the
`test` check to pass before merging. Use feature branches + PRs from now on.

## 2. Metrics

Already wired into `app.py` — page views, pipeline runs, run time, data errors
and the last portfolio Sharpe are served on port 8000 at `/metrics`.

## 3. Docker (local)

```bash
docker build -t hedge-fund-sim .
docker run -p 8501:8501 -p 8000:8000 hedge-fund-sim
# app: http://localhost:8501   metrics: http://localhost:8000/metrics
```

## 4. Prometheus + Grafana (local)

```bash
docker compose up --build
```
Grafana → http://localhost:3000 (admin/admin) → folder **Hedge Fund Simulator**.

## 5. CI/CD (GitHub Actions)

Nothing to configure for lint/test/build — pushing to `main` builds and pushes
`ghcr.io/chitu09/hedge-fund-simulator` with `sha-xxxxxxx`, `main`, `latest`
(and `1.0.0` for a `v1.0.0` tag).

After the first push: GitHub → your profile → **Packages → hedge-fund-simulator →
Package settings → Change visibility → Public** (so Azure can pull without a
registry secret).

The deploy job is skipped until step 7 adds the Azure secret.

## 6. Terraform (Azure infra)

```bash
az login
cd terraform
cp terraform.tfvars.example terraform.tfvars   # put your subscription id in
terraform init
terraform plan
terraform apply
```

* `deploy_aks = true` → AKS cluster (1 × Standard_B2s, Free control plane)
* `deploy_app_service = true` → single-container Azure Web App instead (cheaper, no Kubernetes)

**Cost:** an AKS node runs 24/7. Run `terraform destroy` after your demo/viva.

## 7. Kubernetes (AKS) + CD

```bash
az aks get-credentials -g hfsim-rg -n hfsim-aks
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/
kubectl -n hedge-fund get svc hedge-fund-sim     # EXTERNAL-IP → open in browser
```

To let GitHub Actions deploy automatically:

```bash
az ad sp create-for-rbac --name hfsim-gh --role contributor \
  --scopes /subscriptions/<SUB_ID>/resourceGroups/hfsim-rg --json-auth
```
* Repo → Settings → Secrets → Actions → `AZURE_CREDENTIALS` = that JSON
* Repo → Settings → Variables → `AKS_RESOURCE_GROUP=hfsim-rg`, `AKS_CLUSTER_NAME=hfsim-aks`

Every push to `main` now: test → build → push → `kubectl set image` → rollout.

### Prometheus + Grafana on AKS

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm install monitoring prometheus-community/kube-prometheus-stack -n monitoring --create-namespace
kubectl -n monitoring port-forward svc/monitoring-grafana 3000:80
```
```bash
kubectl apply -f monitoring/servicemonitor.yaml   # tells Prometheus to scrape the app
```
Grafana login: user `admin`, password from
`kubectl -n monitoring get secret monitoring-grafana -o jsonpath="{.data.admin-password}" | base64 -d`.
Then **Dashboards → Import** → `monitoring/grafana/dashboards/hedge-fund.json`.

## 8. Streamlit Community Cloud

Already live. It redeploys on every push to `main`, so it keeps working
alongside Azure — keep it as the free public link.
