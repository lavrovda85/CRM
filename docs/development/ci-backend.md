# CI: backend tests

GitHub Actions workflow: [`.github/workflows/backend-tests.yml`](../../.github/workflows/backend-tests.yml).

- Поднимает **PostgreSQL 16** (сервисный контейнер).
- Задаёт `DATABASE_URL` / `DATABASE_URL_SYNC` для async и Alembic.
- Выполняет **`alembic upgrade head`**, затем:
  - **`pytest -m "not integration"`** — быстрые тесты;
  - **`pytest -m integration`** — жизненный цикл задач через БД и MCP.

Локально без Docker: см. [`docs/testing/TEST_REPORT.md`](../testing/TEST_REPORT.md) и `SKIP_DB_INTEGRATION`.
