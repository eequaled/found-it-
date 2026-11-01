# FoundIt

Async FastAPI/PostgreSQL lost-and-found backend with generated asyncpg queries.
The existing frontend prototype is reconstructed separately on
`integratedapp_proto`; it is not part of this branch.

## Runtime foundation

Requires Python 3.12+ and PostgreSQL 16. Currently only `/health`, `/docs` and
`/openapi.json` are implemented; report, claim and admin routes are later
reconstruction units.

```sh
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[test]'
cp .env.example .env
# Set the database URL and a fresh random admin key in .env.
uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000
```

Settings use the `FOUNDIT_` prefix. Startup fails if PostgreSQL is unavailable;
an already-running API returns 503 from `/health` when database access fails.
The pool has bounded startup, acquisition, query and graceful shutdown times.
`FOUNDIT_ADMIN_KEY` is required by the existing settings even though admin
authentication is not implemented yet.

## Tests

```sh
export TEST_DATABASE_URL='postgresql://user:password@localhost:5432/foundit_test'
pytest -q
```

The suite includes a real PostgreSQL lifespan test; the request-level tests mock
the pool. Do not commit `.env`, real credentials or uploaded files.

## Generation

The generator is a pinned dependency, not vendored source:

- `sqlc` 1.31.1.post1, provided by `sqlc-bin`.
- [`sqlc-gen-better-python`](https://github.com/rayakame/sqlc-gen-better-python)
  v0.9.0, consumed as a checksum-pinned WASM artifact.

```text
migrations/                            handwritten schema migrations
app/db/queries/health.sql              handwritten fixture query
app/db/generated/                      generated asyncpg adapter, checked in
scripts/prepare_plugin.py              fetch/verify the pinned WASM artifact
scripts/codegen.py                     validate SQL and check generated drift
```

```sh
make generate          # fetch/verify the WASM artifact, then run sqlc generate
make validate          # sqlc compile against the current schema and queries
make check-generated   # regenerate independently and reject drift
make test              # validate, check drift, lint and run tests
```

The fixture is deliberately minimal: a no-op schema migration and a
`HealthProbe` query selecting the integer constant `1`. It exists only to prove
the pinned generator and asyncpg output work end to end. The drift check
regenerates in a temporary tree and compares byte-for-byte with the committed
output, so stale or hand-edited generated code fails.

The upstream asyncpg test fixture emits a `v0.8.0` header even though it belongs
to the pinned v0.9.0 source tree. The checksum is pinned and generated headers are
not edited by hand.

## Next unit

Docker Compose, dbmate-backed migrations and an isolated migration-backed test
database are the next foundation review unit.

## Third-party notices

`sqlc-gen-better-python` is MIT-licensed, copyright 2025-present Rayakame. It is
not vendored; `scripts/prepare_plugin.py` verifies its pinned source revision and
the SHA-256 digest of the upstream test fixture before copying the WASM artifact
into the ignored build directory. See the upstream repository for the full
license text.
