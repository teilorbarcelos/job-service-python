# Job Service Python

> Esqueleto (boilerplate) para execução de jobs agendados em Python.
> Conecta-se ao `backend-python` para consumir PostgreSQL, Redis e RabbitMQ.

---

## 🎯 O que é

Skeleton para quem precisa rodar jobs recorrentes (cron) em Python — sem
toda a complexidade de um backend HTTP completo. O backend continua sendo
dono do schema, migrations e ciclo de vida do banco. Os jobs apenas
**consomem** esses serviços para executar tarefas agendadas (limpezas,
sincronizações, health checks, ETL, etc.).

### Stack

- **Python 3.12+** com asyncio
- **APScheduler** (`AsyncIOScheduler` + `CronTrigger`) para cron
- **asyncpg** para PostgreSQL
- **redis.asyncio** para Redis
- **aio-pika** para RabbitMQ
- **pydantic-settings** para validação de env vars
- **pytest** + **pytest-asyncio** + **pytest-mock** para testes
- **coverage.py** com `fail_under = 100`
- **ruff** para lint/format
- **mypy** para typecheck
- **SonarQube** para quality gate

---

## 🚀 Quick Start

```bash
# 1. Instalar dependências
make setup

# 2. Configurar ambiente
cp .env.example .env
# (opcional) edite DATABASE_URL, REDIS_HOST, RABBIT_URL conforme necessário

# 3. Subir infra (PG + Redis + RabbitMQ)
make infra-up

# 4. Rodar o job runner
make dev
```

A cada minuto você verá:
```
[HealthCheck 2026-...] postgres=up redis=up rabbitmq=disabled
```

Com `MESSAGING_ENABLED=true`:
```
[HealthCheck 2026-...] postgres=up redis=up rabbitmq=up
```

---

## ➕ Como adicionar um novo job

### 1. Criar o job

```python
# src/jobs/cleanup_old_records.py
from src.core import BaseJob, JobContext

class CleanupOldRecordsJob(BaseJob):
    name = "cleanup-old-records"
    schedule = "0 3 * * *"               # todo dia às 3h
    description = "Remove registros com mais de 90 dias"

    async def handle(self, context: JobContext) -> None:
        context.logger.info("Starting cleanup")
        # sua lógica aqui
        context.logger.info("Cleanup done")
```

### 2. Registrar

```python
# src/jobs/register_jobs.py
from src.core import Scheduler, SchedulerOptions
from src.jobs.cleanup_old_records import CleanupOldRecordsJob
# ... outros jobs

def register_jobs() -> Scheduler:
    jobs = [
        HealthCheckJob(DefaultHealthChecker(), schedule=settings.health_check_cron),
        CleanupOldRecordsJob(),  # ← novo
    ]
    return Scheduler(jobs, SchedulerOptions(execution_timeout_s=settings.job_execution_timeout_s))
```

### 3. Testar

```python
# tests/jobs/test_cleanup_old_records.py
import pytest
from src.jobs.cleanup_old_records import CleanupOldRecordsJob

def test_job_has_correct_metadata():
    job = CleanupOldRecordsJob()
    assert job.name == "cleanup-old-records"
    assert job.schedule == "0 3 * * *"
    assert job.enabled is True
```

---

## 🏛️ Arquitetura

```
src/
├── app.py                          # Bootstrap (conecta + inicia scheduler)
├── main.py                         # Entry point (asyncio.run)
├── core/
│   ├── base_job.py                 # Classe abstrata de todo job
│   ├── scheduler.py                # Wrapper sobre APScheduler
│   └── __init__.py
├── infra/
│   ├── database/db.py              # asyncpg pool singleton
│   ├── messaging/rabbitmq_provider.py  # aio-pika publisher + check
│   ├── redis/redis_provider.py     # redis.asyncio singleton
│   └── health/default_health_checker.py
├── jobs/
│   ├── health_check_job.py         # Exemplo: status dos 3 serviços a cada minuto
│   └── register_jobs.py            # Registro central
└── shared/
    ├── config/settings.py          # Pydantic Settings
    ├── exceptions.py               # AppError hierarchy
    └── utils/
        ├── logging.py              # JSON structured logger
        ├── shutdown.py             # SIGTERM/SIGINT handlers
        └── signals.py              # wait_with_timeout helper
```

### Fluxo de uma execução

```
cron tick (ex: a cada minuto)
   │
   ▼
Scheduler.execute(name)
   │  - se já rodando, skip (sem overlap)
   │  - cria AbortController (asyncio.Event) com timeout
   ▼
BaseJob.run(signal)
   │  - log: job.start
   ▼
handle({ logger, signal })
   │  - sua lógica aqui
   │  - respeite signal.is_set() para cancelamento via timeout
   ▼
log: job.success (ou job.error)
   │
   ▼
finally: clearTimeout, remove de `running`
```

---

## 🧪 Qualidade

```bash
make lint         # ruff
make typecheck    # mypy
make test         # pytest
make coverage     # pytest --cov (fail_under=100)
make check        # lint + typecheck + test
make sonar        # SonarQube scanner
```

Padrão: **100% de cobertura em `src/`** (excluindo `src/main.py`).
Pipeline roda no pre-commit (Husky) e no CI.

### SonarQube

Quality gate configurado em `sonar-project.properties`:
- 0 bugs, 0 vulnerabilidades, 0 code smells
- Coverage ≥ 80% (atualmente 100%)
- Security & Reliability rating 1.0

---

## ⚙️ Variáveis de ambiente

| Variável | Default | Descrição |
|----------|---------|-----------|
| `ENVIRONMENT` | `local` | `local` / `development` / `test` / `production` |
| `LOG_LEVEL` | `info` | `fatal` / `error` / `warn` / `info` / `debug` / `trace` |
| `SHUTDOWN_TIMEOUT_S` | `30` | Timeout do graceful shutdown |
| `JOB_EXECUTION_TIMEOUT_S` | `300` | Timeout por execução de job |
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgrespw@localhost:5432/backend_python` | Connection string PG |
| `DATABASE_POOL_MAX` | `20` | Pool size |
| `DATABASE_COMMAND_TIMEOUT_S` | `10` | Timeout de query |
| `REDIS_HOST` | `redis://:@localhost:6379` | Host ou URL `redis://` |
| `REDIS_PORT` | `6379` | Porta |
| `REDIS_PASSWORD` | `""` | Senha |
| `REDIS_DB` | `0` | Database number |
| `REDIS_COMMAND_TIMEOUT_S` | `5` | Timeout de comandos |
| `MESSAGING_ENABLED` | `false` | Habilita RabbitMQ |
| `RABBIT_URL` | `amqp://guest:guest@localhost:5672/` | URL do RabbitMQ |
| `RABBIT_USER` | `guest` | Usuário |
| `RABBIT_PASSWORD` | `guest` | Senha |
| `RABBITMQ_PUBLISH_TIMEOUT_S` | `5` | Timeout de publish |
| `HEALTH_CHECK_CRON` | `*/1 * * * *` | Cron do health check |
| `HEALTH_CHECK_ENABLED` | `true` | Liga/desliga o health check |

---

## 🐳 Docker

```bash
# Sobe só a app (assume que PG/Redis/Rabbit já rodam)
docker compose up -d app

# Ou sobe a stack completa isolada
make infra-up
docker compose up -d app
```

A app aponta para `host.docker.internal` por padrão. Para mudar, edite `docker-compose.yml`.

---

## 📚 Referências

- `backend-python/` — origem deste boilerplate
- `job-service-node/` — irmão gêmeo em TypeScript, referência arquitetural
- `TODO.md` — roadmap e próximos passos
