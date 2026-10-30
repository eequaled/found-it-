# FoundIt generation tooling

This branch contains the SQL-to-Python generation integration used by FoundIt.
It is not the FoundIt application: the backend is reconstructed on `dev`, and
the existing frontend prototype is reconstructed on `integratedapp_proto`.

The generator is a pinned dependency, not vendored source:

- `sqlc` 1.31.1.post1, provided by `sqlc-bin`.
- [`sqlc-gen-better-python`](https://github.com/rayakame/sqlc-gen-better-python)
  v0.9.0, consumed as a checksum-pinned WASM artifact.

## Layout

```text
generation/queries/health.sql          handwritten fixture query
generation/schema/*.sql                minimal existing schema fixture
generation/generated/                  generated asyncpg adapter, checked in
scripts/prepare_plugin.py              fetch/verify the pinned WASM artifact
scripts/codegen.py                     validate SQL and check generated drift
tests/test_toolchain.py                exercise the adapter against PostgreSQL
```

The fixture is deliberately minimal: a no-op schema migration and a
`HealthProbe` query selecting the integer constant `1`. It exists only to prove
the pinned generator and asyncpg output work end to end.

## Requirements

Python 3.12+ and PostgreSQL 16 for the generated-adapter test. The generator
artifact is downloaded into the ignored `.tools/` directory; upstream source is
cloned into the ignored `references/` directory.

## Commands

```sh
python3.12 -m venv .venv
. .venv/bin/activate
make install

make generate          # fetch/verify the WASM artifact, then run sqlc generate
make validate          # sqlc compile against the fixture
make check-generated   # regenerate independently and reject drift
make test              # validate, check drift, lint and run tests
```

`make test` needs a reachable PostgreSQL 16 database:

```sh
export TEST_DATABASE_URL='postgresql://foundit:foundit@localhost:5432/foundit_test?sslmode=disable'
```

The upstream asyncpg test fixture emits a `v0.8.0` header even though it belongs
to the pinned v0.9.0 source tree. The checksum is pinned and generated headers are
not edited by hand.

## Third-party notices

`sqlc-gen-better-python` is MIT-licensed, copyright 2025-present Rayakame. It is
not vendored; `scripts/prepare_plugin.py` verifies its pinned source revision and
the SHA-256 digest of the upstream test fixture before copying the WASM artifact
into the ignored build directory. See the upstream repository for the full
license text.
