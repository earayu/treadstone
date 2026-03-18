---
name: database-migration
description: Database model design and Alembic migration workflow for Treadstone. Use whenever adding or modifying SQLAlchemy models, generating Alembic migrations, or applying schema changes to Neon. Also use when the user mentions "migration", "add table", "add column", "schema change", "database model", or any task involving treadstone/models/.
---

# Database Model & Migration Workflow

How to add or change database models in Treadstone and safely apply them to Neon Postgres via Alembic.

## The Golden Rule

**Never modify a production database by hand.** All schema changes flow through:

```
SQLAlchemy model → Alembic autogenerate → review migration → apply to test branch → verify → apply to production
```

## Quick Reference

```bash
# After modifying models
make migration MSG="add users table"   # Generate migration
make migrate                           # Apply to DB
make downgrade                         # Rollback if needed
```

---

## Step 1: Design the Model

Create or modify files in `treadstone/models/`.

### File Structure

```
treadstone/models/
├── __init__.py     # Re-exports all models (critical for Alembic)
├── user.py         # User, OAuthAccount, Invitation
├── api_key.py      # ApiKey
└── <new_model>.py  # Your new model
```

### Model Template

```python
# treadstone/models/example.py
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
| `String(24)` primary key with prefix (`"user"`, `"key"`, `"ex"`) | Human-readable IDs, no UUID overhead |
| `gmt_created` / `gmt_updated` / `gmt_deleted` timestamps | Consistent audit trail, soft-delete support |
| `ForeignKey(..., ondelete="cascade")` | Prevent orphan rows |
| `DateTime(timezone=True)` | Always store timezone-aware timestamps |
| Use `Mapped[...]` + `mapped_column()` | Modern SQLAlchemy 2.0 style with type safety |
| Use `StrEnum` (not `str, Enum`) | Python 3.12+ idiomatic, passes ruff UP042 |
| Soft-delete via `gmt_deleted` column | Prefer soft-delete over hard-delete for important data |

### Relationship with Joined Eager Loading

When a model has `relationship(..., lazy="joined")` (like `User.oauth_accounts`), all queries returning that model need `.unique()` before extracting results:

```python
result = await session.execute(select(User))
users = result.unique().scalars().all()  # .unique() required!
```

Without `.unique()`, SQLAlchemy raises `InvalidRequestError`. This is easy to miss and the error message is not obvious.

---

## Step 2: Register the Model

Every new model file **must** be imported in `treadstone/models/__init__.py`. Alembic's autogenerate only detects models that are registered with `Base.metadata` at import time.

```python
# treadstone/models/__init__.py
from treadstone.models.api_key import ApiKey
from treadstone.models.example import Example       # <-- add
from treadstone.models.user import Invitation, OAuthAccount, Role, User

__all__ = ["User", "OAuthAccount", "Invitation", "Role", "ApiKey", "Example"]
```

`alembic/env.py` imports `from treadstone.models import *`, so the `__init__.py` re-export is the single point of truth. If you forget this step, `alembic revision --autogenerate` will generate an empty migration.

---

## Step 3: Write Tests First (TDD)

Before generating the migration, write a unit test for the model:

```python
# tests/unit/test_example_model.py
from treadstone.models.example import Example


def test_example_fields_exist():
    e = Example()
    assert hasattr(e, "id")
    assert hasattr(e, "name")
    assert hasattr(e, "owner_id")
```

Run it to confirm the model is importable:

```bash
uv run pytest tests/unit/test_example_model.py -v
```

---

## Step 4: Generate the Migration

```bash
make migration MSG="add example table"
```

This runs `alembic revision --autogenerate -m "..."`.

### Review the Generated Migration

**Always review before applying.** Open the generated file in `alembic/versions/` and check:

- [ ] Correct table name and columns
- [ ] Foreign keys point to the right tables
- [ ] Indexes exist on frequently queried columns
- [ ] `nullable` settings match your intent
- [ ] `downgrade()` correctly reverses the changes
- [ ] No unintended changes to existing tables (autogenerate can be noisy)

### Common Autogenerate Pitfalls

| Pitfall | Symptom | Fix |
|---------|---------|-----|
| Model not imported in `__init__.py` | Empty migration (no tables detected) | Add import to `treadstone/models/__init__.py` |
| Using pooled connection string | Intermittent errors during migration | Use direct (non-pooled) connection for Alembic |
| `+asyncpg` in Alembic URL | `RuntimeError: cannot use async engine` | `env.py` already strips `+asyncpg` — don't add it back |
| Enum type changes | Alembic may not detect enum value changes | Handle enum migrations manually |
| Column rename | Autogenerate sees drop + add, not rename | Write manual migration with `op.alter_column()` |

---

## Step 5: Apply to Neon Test Branch First

**Never migrate production directly.** Always test on a Neon branch first.

### Using Neon Branching

```
Production (main branch)
    └── Test branch (fork from main, apply migration here first)
```

Neon branches are copy-on-write and instant to create. The test branch has the same schema and data as production at the time of forking.

### Workflow

1. **Create a test branch** (if not already existing) via Neon Console or CLI
2. **Configure `.env.test`** in `tests/integration/` with the test branch URL (see `tests/integration/README.md`)
3. **Apply migration to test branch:**

```bash
# Point Alembic at the test branch temporarily
# Option A: use .env.test URL
TREADSTONE_DATABASE_URL="<test-branch-url>" make migrate

# Option B: if .env already points to test branch
make migrate
```

4. **Run integration tests** to verify everything works:

```bash
make test-all
```

5. **If tests pass**, apply to production:

```bash
# Point back to production (.env default)
make migrate
```

6. **If tests fail**, fix the model/migration and repeat. Use `make downgrade` on the test branch to rollback, or reset the branch via Neon Console.

---

## Step 6: Commit

```bash
git add treadstone/models/ alembic/versions/ tests/
git commit -m "feat: add example model and migration"
```

Commit the model, migration file, and tests together as one logical unit.

---

## Rollback

```bash
make downgrade          # Rollback last migration
```

For multi-step rollback:

```bash
uv run alembic downgrade -2   # Rollback 2 steps
uv run alembic downgrade base # Rollback to empty
```

To reset a Neon test branch entirely, use the Neon Console "Reset from parent" feature — this is faster than rolling back migrations one by one.

---

## Checklist

Use this checklist when adding any database model change:

- [ ] Model defined in `treadstone/models/<name>.py` with type hints
- [ ] Model imported in `treadstone/models/__init__.py`
- [ ] Unit test written and passing
- [ ] Migration generated with `make migration MSG="..."`
- [ ] Migration file reviewed manually
- [ ] Migration applied to Neon test branch
- [ ] Integration tests passing on test branch (`make test-all`)
- [ ] Migration applied to production
- [ ] Code committed with model + migration + tests together
