# kanbai

A kanban board where **agents and people work side by side**.

This is not a project manager with a bot bolted on top. It is a board designed, from its
very first data model, so that an automated agent and a person are the **same kind of
participant**: both are board members, both move cards, both comment, and both leave a
record of what they did and when.

## The idea

Agent-assisted work tends to break in the same three places:

1. **Nobody knows who did what.** An agent changes something and no one can reconstruct
   why. → Every change produces an **event** signed by its actor.
2. **Two agents do the same thing.** Without coordination, work gets duplicated or
   overwritten. → A card is **claimed** with a deadline; while the claim holds, the card
   belongs to whoever claimed it.
3. **The person cannot step in on time.** → The board is the meeting point: the person
   watches cards move live, reads the card thread, and can release, reassign or reply
   without leaving the interface.

## Domain concepts

| Concept | What it is |
|---------|------------|
| **Actor** | Anyone who participates. Either a **person** or an **agent**. It is who signs every action. |
| **Person** | Human actor. Signs in with email and password and uses the web interface. |
| **Agent** | Automated actor. Authenticates with an API key and uses the API. A person registers it. |
| **Board** | Workspace with its members. A member can be a person or an agent. |
| **Column** | An ordered stage of the flow within a board, with an optional WIP limit. |
| **Card** | The unit of work: it lives in a column and has a position, an author and an assignee. |
| **Claim** | Temporary lock on a card held by an actor, with an expiry. Prevents duplicated work. |
| **Comment** | The card thread. The channel where a person and an agent talk to each other. |
| **Event** | Immutable record of an action: what happened, on what, and who did it. |

## Invariants

These rules are not negotiable for the sake of implementation convenience:

- **An actor is a person or an agent, and the domain never branches on that.** If an
  endpoint needs an `if actor.kind == "agent"` to work, the model is wrong.
- **Every write is attributed to an actor and recorded as an event.**
- **An agent never has more permissions than the person who registered it.**
- **Requesting a resource you are not a member of returns 404**, never 403: we do not
  confirm that it exists.

## Project status

The [board view](docs/features/frontend-tablero.md) is available, with card movement by
mouse or keyboard and rollback on errors. The working board lives in
[`docs/tasks/STATUS.md`](docs/tasks/STATUS.md); each task has its own file under
[`docs/tasks/`](docs/tasks/) and its plan and specification under
[`docs/plans/`](docs/plans/).

## How we work here

Every functional change goes through a four-phase cycle with human approval between each
one (plan → specify → implement → close). The stack, the structure and the coding rules
are in [`AGENTS.md`](AGENTS.md). **Read it before touching anything.**

## Stack

Backend Python 3.14 · FastAPI · SQLAlchemy 2.0 async · PostgreSQL · Alembic, managed with
`uv`. Frontend React 19 · TypeScript · Vite · HeroUI v3 on top of Tailwind v4 · TanStack
Query, with the API types generated from the backend OpenAPI document.

## Getting started from scratch

You need Docker Engine or Docker Desktop with Compose v2. To run the applications on the
host you also need Python 3.14, [uv](https://docs.astral.sh/uv/), Node 24 and npm. No
secrets are required: the Compose credentials are strictly local.

### Full stack with Docker

From the repository root:

```bash
docker compose up -d --build --wait
```

The frontend is served at `http://localhost:5173`, the API at `http://localhost:8000`,
and the API documentation at `http://localhost:8000/docs`. Check availability with
`curl -f http://localhost:8000/api/v1/health/ready` or through the frontend proxy:
`curl -f http://localhost:5173/api/v1/health/ready`.

`docker compose down` stops the services and **keeps** the database. If a port is taken,
copy `.env.example` to `.env` and change only the published ports. Delete data only if
you explicitly decide to, with `docker compose down -v`.

### Development on the host

Start PostgreSQL first, then the two applications in separate terminals:

```bash
docker compose up -d db --wait

cd backend
cp .env.example .env
uv sync --locked --dev
uv run poe migrate
uv run poe dev

cd ../frontend
npm ci
npm run dev
```

The API uses `localhost:5432`; inside Compose the hostname is `db`. To point the Vite
proxy at a different API during development, pass it to the process on startup:
`VITE_PROXY_TARGET=http://localhost:8000 npm run dev`.

Older volumes only ran `docker/postgres/init.sql` when they were created. If
`kanbai_test` is missing, check and create it without dropping the development database:

```bash
docker compose exec db createdb -U kanbai kanbai_test
```

## Quality, migrations and CI

The local gates are `uv run poe check` from `backend/` and `npm run check` from
`frontend/`. Regenerate the contract with `uv run poe openapi` and the types with
`npm run gen:api`; both generated files must leave the tree without differences.
`uv run alembic check` detects models without a migration, and `uv run poe migrate`
applies the existing revisions.

The GitHub Actions workflow runs three jobs: backend quality and migrations against a
real PostgreSQL 18, frontend quality and build, and a full Compose startup. Caches are
invalidated by `uv.lock` and `package-lock.json`; they do not replace any check.
