# Helm Chart — ID Generator

The `openg2p-id-generator` Helm chart deploys the ID Generator service on Kubernetes, following OpenG2P conventions.

## Chart Location

```
charts/openg2p-id-generator/
```

## Prerequisites

- Kubernetes 1.24+
- Helm 3.x
- PostgreSQL (typically `commons-postgresql` in the OpenG2P cluster)
- Istio (optional, for VirtualService routing)

## Dependencies

| Chart | Repository | Purpose |
|---|---|---|
| `common` | `https://openg2p.github.io/openg2p-helm` | Shared templates (labels, names, tplvalues) |
| `postgres-init` | `https://openg2p.github.io/openg2p-helm` | Creates database and user before app starts |

## Installation

### Quick Install

```bash
helm repo add openg2p https://openg2p.github.io/openg2p-helm
helm repo update

helm install id-generator charts/openg2p-id-generator \
  -n <namespace> --create-namespace
```

### Install with Custom ID Types

```bash
helm install id-generator charts/openg2p-id-generator \
  -n trial --create-namespace \
  --set idGenerator.appConfig.idTypes.farmer_id.idLength=6 \
  --set idGenerator.appConfig.idTypes.national_id.idLength=10
```

### Install with Values File Override

```bash
helm install id-generator charts/openg2p-id-generator \
  -n trial --create-namespace \
  -f my-values.yaml
```

Example `my-values.yaml`:

```yaml
global:
  idGeneratorHostname: idgenerator.production.openg2p.org
  postgresqlHost: my-postgresql

idGenerator:
  replicaCount: 3
  appConfig:
    idTypes:
      farmer_id:
        idLength: 6
      household_id:
        idLength: 6
      national_id:
        idLength: 12
    poolMinThreshold: 5000
    poolGenerationBatchSize: 10000
```

### Dry-Run / Debug

```bash
helm install id-generator charts/openg2p-id-generator \
  -n trial --dry-run --debug > out.yaml
```

## Upgrade

```bash
helm upgrade id-generator charts/openg2p-id-generator -n trial
```

To add or remove ID types, update `appConfig.idTypes` in your values and run `helm upgrade`. The pods will restart with the new ConfigMap.

## Uninstall

```bash
helm uninstall id-generator -n trial
```

> **Note**: The database and its data are preserved after uninstall (managed by `postgres-init` with `resource-policy: keep`).

## Configuration Reference

### Global Parameters

| Parameter | Description | Default |
|---|---|---|
| `global.idGeneratorHostname` | Hostname for Istio VirtualService | `idgenerator.trial.openg2p.org` |
| `global.postgresqlHost` | PostgreSQL server host | `commons-postgresql` |
| `global.idGeneratorDB` | Database name (auto-derived from release name) | `{{ .Release.Name \| replace "-" "_" }}` |
| `global.idGeneratorDBPort` | PostgreSQL port | `5432` |
| `global.idGeneratorDBUser` | Database user (auto-derived from release name) | `{{ .Release.Name }}_user` |
| `global.idGeneratorDBSecret` | K8s Secret name holding DB password | `{{ .Release.Name }}` |
| `global.idGeneratorDBUserPasswordKey` | Key in the Secret for DB password | `{{ .Release.Name }}-db-user` |

### ID Generator Parameters

| Parameter | Description | Default |
|---|---|---|
| `idGenerator.enabled` | Deploy the ID Generator | `true` |
| `idGenerator.replicaCount` | Number of pod replicas | `1` |
| `idGenerator.image.repository` | Docker image repository | `openg2p/openg2p-id-generator` |
| `idGenerator.image.tag` | Docker image tag | `develop` |
| `idGenerator.image.pullPolicy` | Image pull policy | `Always` |
| `idGenerator.containerPort` | Container port (uvicorn) | `8000` |
| `idGenerator.service.type` | Kubernetes Service type | `ClusterIP` |
| `idGenerator.service.port` | Service port | `80` |

### Application Config (appConfig)

These values are rendered into a ConfigMap and mounted as the service's YAML config file.

#### ID Types

| Parameter | Description | Default |
|---|---|---|
| `idGenerator.appConfig.idTypes` | Map of ID type name → config. Each ID type gets its own DB table. | See below |
| `idGenerator.appConfig.idTypes.<name>.idLength` | Number of digits in generated IDs (2–32) | — |

Default ID types:

```yaml
idTypes:
  farmer_id:
    idLength: 6
  household_id:
    idLength: 6
```

#### Filter Rules

MOSIP UIN-compliant filter rules applied during ID generation. Adjust only if you understand the impact on ID space and validity.

| Parameter | Description | Default |
|---|---|---|
| `idGenerator.appConfig.sequenceLimit` | Max consecutive sequential digits (e.g., 123) | `3` |
| `idGenerator.appConfig.repeatingLimit` | Max consecutive repeating digits (e.g., 111) | `2` |
| `idGenerator.appConfig.repeatingBlockLimit` | Max repeating digit blocks (e.g., 1212) | `2` |
| `idGenerator.appConfig.conjugativeEvenDigitsLimit` | Max consecutive even digits | `3` |
| `idGenerator.appConfig.digitsGroupLimit` | Max ascending group length | `5` |
| `idGenerator.appConfig.reverseDigitsGroupLimit` | Max descending group length | `5` |
| `idGenerator.appConfig.notStartWith` | Digits the ID must not start with | `["0", "1"]` |
| `idGenerator.appConfig.restrictedNumbers` | Specific numbers to reject | `[]` |

#### Pool Management

| Parameter | Description | Default |
|---|---|---|
| `idGenerator.appConfig.poolMinThreshold` | Minimum available IDs before replenishment triggers | `1000` |
| `idGenerator.appConfig.poolGenerationBatchSize` | IDs generated per replenishment cycle | `5000` |
| `idGenerator.appConfig.poolCheckIntervalSeconds` | Seconds between pool level checks | `30` |
| `idGenerator.appConfig.exhaustionMaxAttempts` | Max consecutive generation failures before marking exhausted | `1000` |
| `idGenerator.appConfig.subBatchSize` | Rows per DB insert transaction (chunking) | `10000` |

### Environment Variables

Set via `idGenerator.envVars` (plain values) and `idGenerator.envVarsFrom` (secret references).

| Variable | Source | Description |
|---|---|---|
| `DB_HOST` | `global.postgresqlHost` | PostgreSQL host |
| `DB_PORT` | `global.idGeneratorDBPort` | PostgreSQL port |
| `DB_NAME` | `global.idGeneratorDB` | Database name |
| `DB_USER` | `global.idGeneratorDBUser` | Database user |
| `DB_PASSWORD` | K8s Secret (secretKeyRef) | Database password |
| `CONFIG_PATH` | Hardcoded | `/app/config/config.yaml` (ConfigMap mount) |

Optional env vars (uncomment in values.yaml to override):

| Variable | Description | Default (in Docker) |
|---|---|---|
| `UVICORN_WORKERS` | Uvicorn workers per pod. Increase for multi-core nodes. | `1` |
| `UVICORN_LOG_LEVEL` | Log level: `debug`, `info`, `warning`, `error`, `critical` | `info` |

### Istio Parameters

| Parameter | Description | Default |
|---|---|---|
| `idGenerator.istio.enabled` | Enable Istio resources | `true` |
| `idGenerator.istio.virtualservice.enabled` | Create VirtualService | `true` |
| `idGenerator.istio.virtualservice.gateway` | Istio gateway name | `internal` |
| `idGenerator.istio.virtualservice.prefix` | URL prefix match | `/v1/idgenerator/` |
| `idGenerator.istio.gateway.enabled` | Create Istio Gateway | `false` |

### Autoscaling Parameters

| Parameter | Description | Default |
|---|---|---|
| `idGenerator.autoscaling.enabled` | Enable HPA | `false` |
| `idGenerator.autoscaling.minReplicas` | Minimum replicas | `1` |
| `idGenerator.autoscaling.maxReplicas` | Maximum replicas | `5` |
| `idGenerator.autoscaling.targetCPUUtilizationPercentage` | CPU threshold for scaling | `80` |
| `idGenerator.autoscaling.targetMemoryUtilizationPercentage` | Memory threshold for scaling | `80` |

### postgres-init Parameters

| Parameter | Description | Default |
|---|---|---|
| `postgres-init.enabled` | Run the database init job | `true` |
| `postgres-init.postgresql.host` | PostgreSQL admin host | `commons-postgresql` |
| `postgres-init.postgresql.existingSecret` | Secret with PostgreSQL admin password | `commons-postgresql` |

## Architecture

### Kubernetes Resources Created

| Resource | Name | Purpose |
|---|---|---|
| ConfigMap | `<release>-config` | Application config YAML (ID types, filters, pool settings) |
| Deployment | `<release>` | ID Generator pods |
| Service | `<release>` | ClusterIP service (port 80 → 8000) |
| Secret | `<release>` | Auto-generated DB user password (pre-install hook) |
| Job | `<release>-postgres-init-*` | Creates database and user |
| VirtualService | `<release>` | Istio routing (if enabled) |
| HPA | `<release>` | Horizontal Pod Autoscaler (if enabled) |

### Startup Sequence

1. **postgres-init Job** — Creates the database and user in PostgreSQL
2. **Init container (postgres-checker)** — Waits until the database is accessible with the correct credentials (loops `psql SELECT 1`)
3. **Main container** — Starts the ID Generator service, creates ID type tables, fills the initial pool
4. **Startup probe** — Waits up to 5 minutes (30 × 10s) for the service to be ready

### Adding / Removing ID Types

To change ID types after initial deployment:

1. Update `idGenerator.appConfig.idTypes` in your values
2. Run `helm upgrade` — this updates the ConfigMap
3. Pods restart and pick up the new config
4. New ID type tables are created automatically
5. Removed ID types are deactivated (tables are preserved in the database)

## Manual Installation (Rancher UI)

The chart includes a `questions.yaml` for Rancher's Helm UI, which presents a guided installation form with the following groups:

- **General** — Hostname, PostgreSQL host, enable/disable components
- **Database** — Database name, user, secret references
- **ID Types** — ID generation types and their config
- **Pool Management** — Pool thresholds and batch sizes
- **Image** — Docker image repository and tag
- **Scaling** — Replica count and HPA settings
