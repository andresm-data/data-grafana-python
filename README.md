# Observabilidad con Grafana + Prometheus + Loki + Python 3.14

Este proyecto despliega un stack de monitoreo completo en Docker para una aplicacion Python 3.14 que:

- expone metricas personalizadas con `prometheus_client`
- envia logs estructurados a Loki
- visualiza todo en Grafana

## 1. Arquitectura

Componentes:

- `python-app`:
  - expone metricas en `:8000/metrics`
  - genera logs estructurados en formato JSON
  - envia logs a Loki por HTTP push API
- `prometheus`:
  - scrapea metricas de `python-app` y de si mismo
- `loki`:
  - almacena y sirve logs para consultas
- `grafana`:
  - panel de visualizacion
  - se conecta a Prometheus (metricas) y Loki (logs)
- `node-exporter`:
  - expone metricas del host (CPU, RAM, disco, red)
- `cAdvisor`:
  - expone metricas por contenedor (CPU, memoria, I/O)

Flujo:

1. `python-app` incrementa metricas y publica `/metrics`
2. Prometheus recolecta esas metricas periodicamente
3. `python-app` envia logs estructurados a Loki
4. Grafana consulta Prometheus y Loki para dashboards
5. Prometheus recolecta metricas de host y contenedores via `node-exporter` y `cAdvisor`

## 2. Estructura del proyecto

```text
.
├── docker-compose.yaml
├── README.md
├── app
│   ├── app.py
│   ├── Dockerfile
│   └── requirements.txt
└── config
    ├── loki-config.yml
    └── prometheus.yml
```

## 3. Archivos clave

### 3.1 `app/requirements.txt`

Dependencias de la app:

- `prometheus_client`
- `python-logging-loki`

### 3.2 `app/app.py`

Incluye:

- metricas custom:
  - `app_requests_total{status="success|error"}`
  - `app_request_latency_seconds` (histograma)
  - `app_temperature_celsius` (gauge)
  - `app_errors_total{type="synthetic_exception"}`
- logs estructurados JSON con etiquetas enviadas a Loki

### 3.3 `config/prometheus.yml`

Configura scrapes para:

- `prometheus:9090`
- `python-app:8000`

### 3.4 `config/loki-config.yml`

Configuracion base de Loki en modo monolitico para laboratorio local.

### 3.5 `docker-compose.yaml`

Levanta:

- `grafana` en `3000`
- `prometheus` en `9090`
- `loki` en `3100`
- `python-app` en `8000`
- `node-exporter` en red interna (puerto interno `9100`)
- `cAdvisor` en red interna (puerto interno `8080`)

Incluye red interna `monitoring` y volumen persistente `grafana-data`.

## 4. Despliegue paso a paso

Desde la raiz del proyecto:

```bash
docker compose up -d
```

Tambien puedes usar el comando clasico (si tu entorno lo tiene):

```bash
docker-compose up -d
```

Verifica estado:

```bash
docker compose ps
```

Ver logs:

```bash
docker compose logs -f python-app
docker compose logs -f loki
docker compose logs -f prometheus
docker compose logs -f grafana
```

## 5. Acceso a Grafana

- URL: `http://localhost:3000`
- Usuario por defecto: `admin`
- Password por defecto: `admin`

## 6. Configurar Data Sources en Grafana

### 6.1 Prometheus

1. Ir a `Connections` -> `Data sources` -> `Add data source`
2. Elegir `Prometheus`
3. URL:

```text
http://prometheus:9090
```

4. Click en `Save & test`

### 6.2 Loki

1. Ir a `Connections` -> `Data sources` -> `Add data source`
2. Elegir `Loki`
3. URL:

```text
http://loki:3100
```

4. Click en `Save & test`

Nota: No necesitas instalar un plugin externo de Loki. El datasource de Loki ya es soportado de forma nativa por Grafana.

## 7. Crear dashboard basico (metricas + logs)

### 7.1 Panel de metricas

1. `Dashboards` -> `New` -> `New dashboard` -> `Add visualization`
2. Selecciona datasource `Prometheus`
3. Usa una consulta como:

```promql
sum by (status) (rate(app_requests_total[1m]))
```

4. Tipo recomendado: `Time series`
5. Guarda el panel como `Request rate by status`

Opcionales utiles:

```promql
histogram_quantile(0.95, sum(rate(app_request_latency_seconds_bucket[5m])) by (le))
```

```promql
app_temperature_celsius
```

### 7.2 Panel de logs

1. `Add visualization`
2. Selecciona datasource `Loki`
3. Consulta inicial:

```logql
{app="python-demo"}
```

4. Para filtrar errores:

```logql
{app="python-demo", level="error"}
```

5. Guarda el panel como `Python structured logs`

## 8. Dashboard de recursos del host y contenedores

Usa datasource `Prometheus` y crea paneles con estas consultas.

### 8.1 CPU del host (%)

```promql
100 - (avg(rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)
```

### 8.2 Memoria usada del host (%)

```promql
100 * (1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes))
```

### 8.3 Disco usado del host (%)

```promql
100 * (1 - (node_filesystem_avail_bytes{fstype!~"tmpfs|overlay"} / node_filesystem_size_bytes{fstype!~"tmpfs|overlay"}))
```

### 8.4 CPU por contenedor

```promql
sum by (name) (rate(container_cpu_usage_seconds_total{name!="",image!=""}[5m]))
```

### 8.5 Memoria por contenedor

```promql
sum by (name) (container_memory_working_set_bytes{name!="",image!=""})
```

## 9. Validaciones rapidas

Comprobar endpoint de metricas:

```bash
curl http://localhost:8000/metrics | grep app_
```

Comprobar que la app emite logs:

```bash
docker compose logs --tail=50 python-app
```

Comprobar targets de Prometheus (incluye host/contenedores):

```bash
curl -s http://localhost:9090/api/v1/targets | grep -E 'node-exporter|cadvisor|python-app|prometheus'
```

## 10. Troubleshooting

- Error de montaje tipo `not a directory`:
  - Verifica que en `docker-compose.yaml` el origen sea archivo y el destino tambien archivo.
- Data source no conecta:
  - Recuerda usar nombres de servicio Docker (`prometheus`, `loki`) desde Grafana, no `localhost`.
- Mensaje de plugin incompatible de Loki:
  - No instales plugin externo de Loki; usa el datasource nativo.
- `node-exporter` o `cAdvisor` en estado `down`:
  - Revisa `docker compose logs node-exporter` y `docker compose logs cadvisor`.
  - En entornos Linux con politicas de seguridad estrictas, `cAdvisor` puede requerir permisos elevados (ya incluidos en el compose).

## 11. Apagar y limpiar

Detener stack:

```bash
docker compose down
```

Detener y borrar volumenes (incluye datos de Grafana):

```bash
docker compose down -v
```
