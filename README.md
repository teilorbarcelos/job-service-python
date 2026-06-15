# Backend Python — Boilerplate de Alta Escalabilidade

Boilerplate backend Python pronto para produção com FastAPI, SQLAlchemy, Redis, RabbitMQ e Prometheus/Grafana. Arquitetura modular em camadas com **SOLID**, **DRY**, **Quality Gate SonarQube verde** e **Outbox Pattern** para eventos assíncronos.

## 📊 Status do Boilerplate

| Categoria | Status |
|-----------|--------|
| **Testes unitários** | ✅ 318 passing |
| **Compliance suite** | ✅ 51/51 passing |
| **SonarQube quality gate** | ✅ 0 violações, 100% hotspots revisados |
| **Cobertura de testes** | 96.53% (gaps pre-existentes em `settings.py`, `logging.py`, `exceptions.py`) |
| **Auth + Rate limit + Outbox** | ✅ Production-ready |
| **SOLID/DRY/Protocols** | ✅ Aplicado nos providers (Redis, RabbitMQ, Storage) |

## 🚀 Getting Started

### 1. Requirements
- Python 3.12+
- Docker and Docker Compose (for infrastructure)

### 2. Environment Setup

You can set up the environment manually or use the **Makefile** (recommended).

**Using Makefile:**
```bash
make setup
```

**Manually:**
Create and activate the virtual environment, then install the dependencies:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Quick Commands (Makefile)

To simplify daily tasks, we've created a `Makefile` with short commands:

| Command | Description |
| :--- | :--- |
| `make dev` | Inicia o ambiente de desenvolvimento (Hot Reload) |
| `make test` | Executa a suíte de testes unitários e de integração |
| `make coverage` | Executa os testes e exibe relatório de linhas não cobertas |
| `make check` | Executa lint + typecheck + test |
| `make lint` | Ruff check |
| `make format` | Ruff format |
| `make typecheck` | Mypy type check |
| `make security` | Bandit + Safety scan |
| `make sonar` | SonarQube scanner |
| `make generate name=X` | Gera novo módulo + migration Alembic automática |
| `make storage-driver name=X` | Gera driver de storage (s3, gcs, azure) |
| `make infra-up` | Sobe PostgreSQL, Redis, RabbitMQ no Docker |
| `make infra-down` | Derruba containers da infraestrutura |
| `make metrics-up` | Sobe Prometheus & Grafana |
| `make metrics-down` | Derruba stack de métricas |
| `make db-migrate` | Gera script de migração Alembic |
| `make db-upgrade` | Aplica migrações pendentes |
| `make clean` | Remove arquivos temporários e venv |

---

### 4. Module Generation

The project includes a professional module generator that ensures architectural consistency and **100% initial test coverage**.

To create a new module (e.g., `Category`):
```bash
make generate
```

**What happens:**
1.  **Interactive Prompt**: The script asks for the module name if not provided.
2.  Creates `src/modules/category/` with all layers (Model, Repository, Service, Schemas, Router).
3.  Creates `tests/modules/category/test_category_router.py` with full CRUD tests.
4.  Automatically registers the Model in the database engine.
5.  Automatically registers the Router in `main.py`.

---

### 5. Development Workflow (Step-by-Step)

To add a new feature to the system, follow these steps:

1.  **Generate the Module**:
    `make generate name=MyFeature`
2.  **Define the Model**:
    Go to `src/modules/my_feature/models.py` and add the specific columns you need.
3.  **Update Schemas**:
    Adjust `src/modules/my_feature/schemas.py` to include your new fields in the DTOs.
4.  **Create Migration**:
    `make db-migrate` (Alembic will detect your new model/fields automatically).
5.  **Apply Migration**:
    `make db-upgrade` (This updates your PostgreSQL database).
6.  **Run Tests**:
    `make test` (Ensure the auto-generated tests still pass with your changes).

---

### 6. Advanced Filtering & Search

The system implements a powerful dynamic filtering system in the `BaseService`, providing full parity with the legacy PHP Slim implementation:

- **Exact Match**: `?name=Value`
- **Partial Match (Contains)**: Handled automatically for configured fields.
- **Date Ranges**: Use `_start` and `_end` parameters (e.g., `?created_at_start=2023-01-01&created_at_end=2023-12-31`).
- **Global Search**: Use `searchWord=term` to search across all allowed fields simultaneously.
- **Pagination**: Use `page=0&size=10` (Zero-based indexing).

---

### 7. Testing Guide

To run the tests, you **do not need** the Docker database to be running.

**Features:**
- **Isolated DB**: Uses a temporary SQLite (`test.db`).
- **Mirrored Structure**: The `tests/` directory perfectly mirrors `src/`. If a file exists at `src/modules/user/router.py`, its test is at `tests/modules/user/test_user_router.py`.
- **Coverage threshold**: `pyproject.toml` configured for `fail_under = 100` (gaps pre-existentes em `settings.py`, `logging.py`, `exceptions.py` precisam ser preenchidos para atingir 100% no novo código).

---

### 8. Database and Migrations
The project uses an **automatic initialization** system. When running the backend (`make dev`):
- **Migrations**: SQLAlchemy will automatically create all tables in PostgreSQL.
- **Seeds**: The system will run `bootstrap_system`, performing an **Upsert** of Roles, Features, and the Initial Administrator User defined in `.env`.

---

### 9. Documentation
Access the interactive documentation (Swagger) at: `http://localhost:8888/v1/docs`

---

### 10. Security & Access Control (ACL/RBAC)

The system implements a multi-layered security infrastructure, combining state-of-the-art authentication with granular permission control:

#### 🔐 Real-time Session Management (Redis)
Unlike traditional stateless JWT implementations, this system uses **Redis** to provide instant session control:
- **Instant Revocation**: When a user is updated, deactivated, or has their roles/permissions changed, all their active sessions are instantly wiped from Redis.
- **Force Logout**: Security changes take effect in milliseconds across the entire fleet, without waiting for JWT expiration.
- **Hybrid Security**: Combines the performance of JWT with the absolute control of a stateful session.

#### 🛡️ Granular Authorization (Middleware-driven)
Access control is applied declaratively at the route level using a double-middleware strategy:
1.  **AuthMiddleware**: Validates the JWT and ensures the session is active in Redis.
2.  **PermissionMiddleware**: Implements **RBAC (Role-Based Access Control)** by validating if the user has the required permission for the specific feature and action (`view`, `create`, `delete`, `activate`).

#### 📝 Request Validation & Data Integrity
- **Pydantic Schemas**: 100% of incoming requests are validated using strict Pydantic models, ensuring that only correctly formatted and sanitized data reaches the service layer.
- **Automatic Sanitization**: Data is automatically validated and transformed (casted) according to the schema definitions.
- **Audit Logs**: Every security-sensitive action is automatically recorded in the auditing system (see Section 13).

---

### 11. Messaging System (RabbitMQ)

Integração profissional com **RabbitMQ** para processamento assíncrono:

- **`@consumer(queue, exchange, exchange_type)`** decorator para registro declarativo de consumers
- **Publisher confirms** (`mandatory=True`) — garantia de entrega
- **DLQ** (Dead Letter Queue) configurável por fila
- **Suporte a exchanges**: `direct`, `topic`, `fanout`, `headers`
- **Topologia declarada no startup**: exchanges/queues/bindings criados no `setup_topology()`
- **Auto-restart**: consumers reiniciam automaticamente em caso de crash
- **Connection pooling**: `connect_robust` com retry exponencial e timeout

**Configuration (`.env`):**
```env
MESSAGING_ENABLED=true
RABBIT_URL=amqp://guest:guest@localhost:5672/
```

**Exemplo de consumer:**
```python
from src.infra.messaging.rabbitmq_provider import consumer

@consumer(queue="audit", exchange="audit", exchange_type="direct")
async def handle_audit_event(message: dict):
    await audit_service.save_audit(message)
```

---

### 12. Multi-Storage Provider System (Manager/Driver Pattern)

The system provides a modular and professional infrastructure for file storage, using a **Manager/Driver** architecture. This allows total abstraction of the file system, where business logic interacts with a single interface, while the actual driver (Local, S3, GCS, Azure) is resolved dynamically.

#### ⚙️ Main Configuration
Provider switching is done instantly via `.env`:

```env
# Defines the active driver (local, s3, gcs, azure)
STORAGE_DISK=local

# Base public URL to generate file access links
STORAGE_URL=http://localhost:8888/storage
```

#### 🛠️ Driver Management (`make storage-driver`)
To keep the project lightweight, only the `local` driver comes pre-installed. You can add support for new providers on demand with a single command:

```bash
# Example to install Amazon S3 support
make storage-driver name=s3

# Example to install Google Cloud Storage support
make storage-driver name=gcs
```

**What the command does automatically:**
1.  **Code Generation**: Creates the Driver file in `src/infra/storage/drivers/` following the system pattern.
2.  **Test Coverage**: Automatically generates a test file with **100% coverage** for the new driver using auto-mocking templates.
3.  **Environment Config**: Injects required keys (e.g., `S3_KEY`, `GCS_BUCKET`) into your `.env` and `.env.example`.
4.  **Dependency**: Adiciona o pacote no `requirements.txt` (PEP 668 friendly — sem `pip install` direto).

#### 🧪 Testing Architecture
The storage system is designed to be testable in isolation:
- **Auto-Mocking**: Generated tests use a `wraps` strategy to ensure 100% line coverage even on placeholder methods.
- **Dynamic Resolution**: `StorageProvider` includes tests ensuring correct resolution even for drivers not yet physically installed.

#### 📡 Health Monitoring
Storage integrity (read/write/delete capability) is monitored in real-time by the `/v1/health` endpoint, ensuring that permission issues or cloud connection failures are detected immediately.

---

### 13. Advanced Auditing & Outbox Pattern

The system uses the **Outbox Pattern** para garantir consistência e resiliência nos eventos de auditoria:

```
Request → Outbox (DB) → Worker assíncrono → RabbitMQ → Audit Service → tb_audit
```

**Funcionamento:**
- **Outbox table**: Eventos de audit são escritos na tabela `outbox` na mesma transação
- **Worker com intervalo adaptativo**: 0.5s quando há eventos pendentes, 5s quando idle (silencioso)
- **Backoff exponencial**: Em caso de falhas consecutivas, espera cresce até 30s (não martela RabbitMQ)
- **Single commit**: `publish()` no modo síncrono faz 1 commit (write + mark processed juntos)
- **Batch update**: `process_pending()` faz 1 update por batch, não 1 por record
- **Fallback síncrono**: Quando `MESSAGING_ENABLED=false`, processa direto no banco sem RabbitMQ

**Componentes:**
- **`AuditMiddleware`**: Captura automaticamente todas as ações autenticadas
- **`tb_audit`**: Registra method, URL, IP, user info e detalhes da ação
- **`tb_error_log`**: Captura exceções não tratadas (500) via global exception handler
- **Auto-Diff**: Armazena estado "antes" e "depois" para updates via `audit_context`
- **Identity Persistence**: Rastreia usuários por UUID, não por email

---

### 14. GitHub Actions (CI)

The project includes a state-of-the-art **Continuous Integration** workflow:
- **Automated Testing**: Every push or PR triggers a full test suite execution.
- **Coverage Validation**: Ensures the project maintains **100% test coverage**.
- **Fast Feedback**: Uses SQLite and mocks for ultra-fast validation without external dependencies.
- **Workflow**: Defined in `.github/workflows/ci.yml`.

---

### 15. SonarQube Quality Gate

O projeto mantém **Quality Gate verde** no SonarQube continuamente:
- **0 violações** no código novo
- **Cobertura ≥ 80%** no código novo
- **100% dos security hotspots revisados**
- **0 duplicações** no código novo

```bash
# Analisar com SonarQube local
make sonar
```

O gateway está configurado em `sonar-project.properties` e integrado ao fluxo de desenvolvimento — todo PR deve manter o quality gate verde.

---

### 16. Real-time Observability (Prometheus & Grafana)

The system includes a state-of-the-art observability layer for real-time monitoring and troubleshooting:

#### 📊 Metrics Stack
- **Prometheus**: Automatically scrapes the `/metrics` endpoint.
- **Grafana**: Pre-configured with a dashboard for RPS, Latency, Status Codes, Memory and CPU.
- **Persistência**: Dados salvos em volumes Docker para evitar perda de histórico.

#### 🏥 Health Checks & Monitoring
- **Deep Health Monitoring**: `/health` endpoint provides real-time status of all critical infrastructure (PostgreSQL, Redis, RabbitMQ, Storage).
- **Liveness & Readiness**: Standardized `/liveness` and `/readiness` endpoints.

---

### 17. PDF Generation Service (Streaming Proxy)

The system includes a high-performance integration for PDF generation, implemented as a **streaming proxy** to ensure maximum efficiency.

#### 🌊 Zero-Memory Streaming
Unlike traditional implementations that load the entire PDF into memory before sending it to the client, this system uses `httpx` and FastAPI's `StreamingResponse` to:
-   **Proxy Bytes Directly**: Bytes are streamed chunk-by-chunk from the microservice to the client.
-   **Low Footprint**: Memory usage remains constant regardless of the PDF size.
-   **Async First**: Fully non-blocking I/O using Python's `async/await`.

#### 🛠️ Configuration
Connectivity is managed via `.env`:
```env
# URL of the PDF rendering microservice (e.g., react-pdf-service)
PDF_SERVICE_URL=http://localhost:8889
```

#### 🔍 Debug & Diagnostics
To facilitate development and troubleshooting, the system exposes environment-protected diagnostic endpoints:
-   **`POST /v1/debug/pdf`**: Generates a PDF based on template and JSON data.
-   **`GET /v1/debug/pdf`**: Generates a sample "Welcome" PDF inline.

---

### 18. API Documentation & Monitoring
Access the interactive documentation and observability tools at:
- **Swagger UI:** `http://localhost:8888/v1/docs`
- **Prometheus UI:** `http://localhost:9090`
- **Grafana Dashboard:** `http://localhost:3001` (User: `admin` / Pass: `admin`)
- **Health Check:** `http://localhost:8888/health`
- **Metrics Endpoint:** `http://localhost:8888/metrics`

---

## 🛠 Architecture & Standards

### 1. Design Patterns
- **Repository Pattern**: Centralizes data access.
- **Service Layer**: Decouples business rules.
- **Generic CRUD**: `BaseRepository` & `BaseService` reduce boilerplate by 70%.
- **Outbox Pattern**: Eventos críticos vão pra `outbox` table (commit) antes de serem processados, garantindo consistência transacional.
- **Protocol-based Dependency Injection**: `RedisProviderInterface`, `RabbitMQProviderInterface`, `StorageDriverInterface` — facilita mocking e LSP.
- **Locality of Tests**: Tests mirror the source code exactly.

### 2. Project Structure (The "Gold Standard")
- **`src/core/`**: Base classes, core abstractions, and shared helpers.
- **`src/infra/`**: Global infrastructure (Database, Redis, Email, Messaging, Outbox, Storage).
- **`src/modules/`**: Self-contained business modules (e.g., `auth`, `user`, `audit`).
- **`src/shared/`**: Global middlewares, protocols/interfaces, and generic config/constants.
- **`tests/`**: Mirror tests for each module and core component.

### 3. Protocol Interfaces (boilerplate-ready)

Todos os providers de infra têm **Protocol interfaces** em `src/infra/<provider>/<provider>_interface.py`:

- `RedisProviderInterface` — usado pelo `MockRedisModule` em tests
- `RabbitMQProviderInterface` — facilita mock e test
- `StorageDriverInterface` — contrato para drivers Local, S3, GCS, Azure

Isso garante **Liskov Substitution Principle** e permite trocar implementações sem mudar o código de negócio.

---

## 🔌 Modo microsserviço (auth-service-python)

O monolith pode delegar toda a autenticação para o **auth-service-python** (FastAPI) — um microsserviço destacado que expõe login, refresh, logout, me, reset de senha e JWKS.

### Diagrama

```
                    ┌──────────────┐
                    │   Cliente    │
                    └──┬───────┬───┘
                       │       │
                 /v1/auth/*   demais rotas
                       │       │
                       ▼       ▼
              ┌────────────┐  ┌──────────────────┐
              │ Auth       │  │ Backend Python   │
              │ (porta     │  │ (porta 8888)     │
              │  8001)     │  │                  │
              │            │  │ /v1/user, /role  │
              │ /login     │  │ /feature, /prod  │
              │ /refresh   │  │ /audit, /outbox  │
              │ /logout    │  │ /storage, /pdf   │
              │ /me        │  └──────────────────┘
              │ /password/…│           │
              │ /jwks      │           │
              └────────────┘           │
                       │               │
                       └───────┬───────┘
                               ▼
                    ┌─────────────────────┐
                    │  PostgreSQL + Redis  │
                    └─────────────────────┘
```

### Passo a passo

```bash
# 1. Inicie o auth-service-python (porta 8001)
cd /home/teilor/MyProjects/mage-boilerplates/auth-service-python
make dev
# ou: ./venv/bin/uvicorn src.main:app --host 0.0.0.0 --port 8001

# 2. Inicie o monolith com AUTH_MODE=remote (porta 8888)
cd /home/teilor/MyProjects/mage-boilerplates/backend-python
AUTH_MODE=remote ./venv/bin/uvicorn src.main:app --host 0.0.0.0 --port 8888

# 3. Use o token do auth-service no monolith
TOKEN=$(curl -s -X POST http://localhost:8001/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@email.com","password":"admin@123"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")
curl -s http://localhost:8888/v1/user -H "Authorization: Bearer $TOKEN"
```

### O que muda

| Aspecto | `AUTH_MODE=local` | `AUTH_MODE=remote` |
|---------|-------------------|-------------------|
| Roteador `/v1/auth/*` | Incluído no monolith | Removido (delegado ao auth-service) |
| Gerenciamento de sessão | Redis no monolith | Redis no auth-service |
| JWT secret | Mesmo processo | Compartilhado via `JWT_SECRET` |
| Compliance | 48/48 testes | 43/48 testes (session invalidation cross-service) |

> ⚠️ **Importante:** Em remote mode, a invalidação de sessão por update de role/user depende de mecanismo extra (webhook/fila) entre os serviços. O compliance espera 100% dos testes em local mode; em remote mode, 5 testes de invalidação cruzada podem falhar.

---

**Tip:** If you are only using `make` commands, you don't need to activate the `venv` in your terminal, as the `Makefile` handles it internally.
