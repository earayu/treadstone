---
name: database-migration
description: Database model design and Alembic migration workflow for Treadstone. Use whenever adding or modifying SQLAlchemy models, generating Alembic migrations, or applying schema changes to Neon. Also use when the user mentions "migration", "add table", "add column", "schema change", "database model", or any task involving treadstone/models/.
---

# Database Model & Migration Workflow

All schema changes flow through this pipeline — never modify a shared database by hand:

```
SQLAlchemy model → Alembic autogenerate → review migration → apply to test branch → verify → apply to target environment
```

Quick reference:

```bash
make migration MSG="add example table"   # Generate migration
make migrate                             # Apply to DB
make downgrade                           # Rollback last migration
```

---

## Step 1: Design the Model

Create or modify files in `treadstone/models/`.

```
treadstone/models/
├── __init__.py     # Re-exports all models (critical for Alembic)
├── user.py         # User, OAuthAccount, Invitation
├── api_key.py      # ApiKey
└── <new_model>.py  # Your new model
```

### Model Template

```python
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from treadstone.core.database import Base
from treadstone.models.user import random_id, utc_now


class Example(Base):
    __tablename__ = "example"

    id: Mapped[str] = mapped_column(
        String(24), primary_key=True, default=lambda: "ex" + random_id()
    )
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    owner_id: Mapped[str] = mapped_column(
        String(24), ForeignKey("user.id", ondelete="cascade"), nullable=False
    )
    gmt_created: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    gmt_deleted: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
```

### Conventions

| Convention | Rationale |
|-----------|-----------|
| `String(24)` PK with prefix (`"user"`, `"key"`, `"ex"`) | Human-readable IDs, no UUID overhead |
| `gmt_created` / `gmt_updated` / `gmt_deleted` timestamps | Consistent audit trail, soft-delete support |
| `ForeignKey(..., ondelete="cascade")` | Prevent orphan rows |
| `DateTime(timezone=True)` | Always store timezone-aware timestamps |
| `Mapped[...]` + `mapped_column()` | Modern SQLAlchemy 2.0 style with type safety |
| `StrEnum` (not `str, Enum`) | Python 3.12+ idiomatic, passes ruff UP042 |
| Soft-delete via `gmt_deleted` | Prefer soft-delete over hard-delete for important data |

### Joined Eager Loading Gotcha

Models with `relationship(..., lazy="joined")` (e.g. `User.oauth_accounts`) require `.unique()` before extracting results, otherwise SQLAlchemy raises `InvalidRequestError`:

```python
result = await session.execute(select(User))
users = result.unique().scalars().all()  # .unique() required!
```

---

## Step 2: Register the Model

Every new model **must** be imported in `treadstone/models/__init__.py`. Alembic autogenerate only detects models registered with `Base.metadata` at import time.

```python
# treadstone/models/__init__.py
from treadstone.models.api_key import ApiKey
from treadstone.models.example import Example       # <-- add
from treadstone.models.user import Invitation, OAuthAccount, Role, User

__all__ = ["User", "OAuthAccount", "Invitation", "Role", "ApiKey", "Example"]
```

If you skip this, `alembic revision --autogenerate` generates an empty migration.

---

## Step 3: Write a Test for the Model

Prefer the smallest test that proves the schema change matters:

- `tests/unit/` for model shape / helper logic
- `tests/integration/` for real DB constraints, indexes, and query behavior
- `tests/api/` when the schema change is surfaced through an API contract

A lightweight unit test is the minimum; use integration coverage when the migration changes persistence behavior.

```python
# tests/unit/test_example_model.py
from treadstone.models.example import Example

def test_example_fields_exist():
    e = Example()
    assert hasattr(e, "id")
    assert hasattr(e, "name")
    assert hasattr(e, "owner_id")
```

```bash
make test
```

---

## Step 4: Generate and Review the Migration

```bash
make migration MSG="add example table"
```

Open the generated file in `alembic/versions/` and verify:

- Correct table name and columns
- Foreign keys point to the right tables
- Indexes on frequently queried columns
- `nullable` settings match intent
- `downgrade()` correctly reverses changes
- No unintended changes to existing tables

### Common Pitfalls

| Pitfall | Symptom | Fix |
|---------|---------|-----|
| Model not in `__init__.py` | Empty migration | Add import to `treadstone/models/__init__.py` |
| Pooled connection string | Intermittent migration errors | Use direct (non-pooled) connection for Alembic |
| `+asyncpg` in Alembic URL | `RuntimeError: cannot use async engine` | `env.py` strips it automatically — don't add it back |
| Enum value changes | Alembic doesn't detect them | Handle enum migrations manually |
| Column rename | Autogenerate sees drop + add | Write manual migration with `op.alter_column()` |

---

## Step 5: Apply to Neon Test Branch First

Never migrate production directly. Neon branches are instant, copy-on-write clones — use one as a staging environment.

```
Shared branch / environment
    └── Test branch (fork, apply migration here first)
```

1. Create a test branch via Neon Console or CLI (if not already existing)
2. Apply migration to the test branch:
   ```bash
   TREADSTONE_DATABASE_URL="<test-branch-url>" make migrate
   ```
3. Run the most relevant verification:
   ```bash
   make test-integration
   ```
   If the change also affects API or unit behavior, run `make test-all`.
4. If tests pass, apply to the shared target branch / environment:
   ```bash
   make migrate
   ```
5. If tests fail, fix and retry. Use `make downgrade` or reset the Neon branch from its parent.

---

## Step 6: Commit

Commit the model, migration file, and tests together as one logical unit:

```bash
git add treadstone/models/ alembic/versions/ tests/
git commit -m "feat: add example model and migration"
```

---

## Rollback

```bash
make downgrade                   # Rollback last migration
uv run alembic downgrade -2      # Rollback 2 steps
uv run alembic downgrade base    # Rollback to empty
```

To reset a Neon test branch entirely, use the Neon Console "Reset from parent" feature.

---

## Checklist

- [ ] Model defined in `treadstone/models/<name>.py` with type hints
- [ ] Model imported in `treadstone/models/__init__.py`
- [ ] Unit test written and passing
- [ ] Integration/API coverage added when the schema change affects real DB behavior
- [ ] Migration generated with `make migration MSG="..."`
- [ ] Migration file reviewed manually
- [ ] Migration applied to Neon test branch
- [ ] Relevant verification passing (`make test-integration` or `make test-all`)
- [ ] Migration applied to the target shared environment
- [ ] Committed together: model + migration + tests
