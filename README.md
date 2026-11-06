# FoundIt

Async FastAPI/PostgreSQL lost-and-found backend with generated asyncpg queries.
The existing frontend prototype is reconstructed separately on
`integratedapp_proto`; it is not part of this branch.

## Local development

Requires Python 3.12+, Node 22+, PostgreSQL 16 and Docker Compose. Use a Python
virtual environment, then:

```sh
cp .env.example .env
# Replace the admin key and DB password; keep all DB settings consistent.
make install
docker compose up -d db
make migrate
make up
```

The host URL uses `localhost`; the container URL uses service name `db`.
URL-encode passwords in URLs. Compose reads `.env`, which is excluded from the
image and from Git. The API listens on port 8000. To run it without Docker
against an existing database:

```sh
uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000
```

Settings use the `FOUNDIT_` prefix. Startup fails if PostgreSQL is unavailable;
an already-running API returns 503 from `/health` when database access fails.
The pool has bounded startup, acquisition, query and graceful shutdown times.
`FOUNDIT_ADMIN_KEY` is required by the existing settings even though admin
authentication is not implemented yet.

## Migrations

`migrations/` holds handwritten, ordered dbmate migrations; applied migrations
are never rewritten. `make migrate` applies pending migrations to the database
named by `FOUNDIT_DATABASE_URL` and `make rollback` reverses exactly one.
`make check-migrations` applies every migration to an owned temporary database,
rolls back one step at a time, re-applies them, then drops that database.

The pinned `dbmate` binary is a dev dependency installed by `make install`; it is
not vendored.

## Tests

Set `TEST_DATABASE_URL` to an existing database on a **local test server**, with
a role allowed to create databases. Tests never roll back or drop that supplied
database: each integration case creates, migrates and drops its own UUID-named
database. Migration checking also uses a disposable database.

```sh
export TEST_DATABASE_URL='postgresql://user:password@localhost:5432/foundit_test'
make test              # lint, SQL/codegen checks, tests and migration roundtrip
make check-migrations  # up, one-by-one rollback, up in an owned temporary DB
make test-ui           # install, test and build the admin shell
```

`make down` stops containers without deleting named volumes. The admin shell
in `admin-ui/` is only a Vite/React placeholder that proxies relative `/api`
requests to port 8000 and has a single component test. Do not commit
`.env`, real credentials or uploaded files.

## Report API

`POST /reports` accepts one JSON report and returns `{id, tracking_token}`. The
raw token is returned once, after commit, and only its SHA-256 digest is stored;
it is not recoverable. New reports are `pending_review` and therefore not public.
`GET /reports/{id}` returns an open report with eight public fields and never
contact details, the digest or moderation notes; any non-open report is
indistinguishable from a missing one. `GET /reports/{id}/status` requires
`X-Tracking-Token` and returns the status with its history. Every response is
`no-store`.

Image validation and private photo storage primitives exist and are
tested, but no endpoint accepts an upload yet.

`GET /reports` is the public search. Keyword, category, type, inclusive
calendar-date bounds, location substring and paging are combined in one
statement, so an empty or out-of-range page still reports the exact total;
results are ordered by rank, then newest, then id. `scripts/seed_search.py`
creates its own disposable database, seeds synthetic reports for planner
measurements and drops it again; it never writes to the database named in
`TEST_DATABASE_URL`.

`POST /reports/{id}/claims` creates a pending claim for an open found report and
returns its one-time token. The claimant name, contact and evidence are never
exposed by a public endpoint, no claim tracking, withdrawal or decision endpoint
exists yet, and bodies are capped before parsing: 64 KiB for claims and the
photo limit plus 64 KiB for report creation. Claims take a `FOR SHARE` lock on
the report and hold it through commit, so report-closing writers wait and a
submission that waited behind one re-reads the fresh status.

## Generation

The generator is a pinned dependency, not vendored source:

- `sqlc` 1.31.1.post1, provided by `sqlc-bin`.
- [`sqlc-gen-better-python`](https://github.com/rayakame/sqlc-gen-better-python)
  v0.9.0, consumed as a checksum-pinned WASM artifact.

```text
migrations/                            handwritten schema migrations
app/db/queries/health.sql              handwritten fixture query
app/db/generated/                      generated asyncpg adapter, checked in
scripts/prepare_plugin.py              download/verify the pinned WASM artifact
scripts/codegen.py                     validate SQL and run sqlc generate
scripts/dbmate.py                      invoke the pinned dbmate binary
scripts/database.py                    disposable test databases
scripts/migrations.py                  migrate, rollback and roundtrip checks
scripts/seed_search.py                 disposable synthetic search fixture
```

```sh
make sqlc-generate     # download/verify the WASM artifact, then run sqlc generate
make validate          # sqlc compile against the current schema and queries
make check-generated   # regenerate and reject any git diff in generated output
make test              # validate, regenerate, lint and run tests
```

The fixture is deliberately minimal: a no-op schema migration and a
`HealthProbe` query selecting the integer constant `1`. It exists only to prove
the pinned generator and asyncpg output work end to end. Regenerating must leave
no git diff in the generated output, so stale or hand-edited generated code
fails.

The upstream asyncpg test fixture emits a `v0.8.0` header even though it belongs
to the pinned v0.9.0 source tree. The checksum is pinned and generated headers are
not edited by hand.

## Third-party notices

`sqlc-gen-better-python` is MIT-licensed, copyright 2025-present Rayakame. It is
not vendored; `scripts/prepare_plugin.py` downloads the single WASM fixture at
the pinned revision and verifies its SHA-256 digest before writing it to the
ignored build directory. See the upstream repository for the full license text.
