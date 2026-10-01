1. Stack: Python 3.12, FastAPI, SQLAlchemy 2.x, PostgreSQL, RabbitMQ via aio-pika, Redis, httpx, tenacity, pybreaker, PyJWT, bcrypt, pytest, testcontainers. Use latest stable versions; after installing, pin the real installed versions in requirements.txt. Never invent package names or APIs; if unsure, check the installed package's docs or source.
2. No hardcoded values: all config (URLs, secrets, ports, DSNs) comes from environment variables via config.py and .env.example.
3. Each service owns its database. Services never import each other's code or touch each other's tables. Only libs/common may be shared.
4. Layering: api -> domain (service logic) -> repositories -> models. No business logic in api files.
5. Every endpoint has Pydantic schemas, correct HTTP status codes, and a consistent error JSON: {"error": {"code": "...", "message": "..."}}.
6. Never change an endpoint or event defined in docs/CONTRACTS.md without asking me.
7. After each task, run the stated verification commands and show real output. Never claim success without running them. Never skip or delete failing tests; fix the cause.
8. If a requirement is ambiguous, ask me instead of guessing.
9. Keep files under 200 lines. No placeholder or TODO code, and no fake or mocked implementations outside tests.
