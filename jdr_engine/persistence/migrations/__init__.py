# jdr_engine/persistence/migrations/__init__.py
from jdr_engine.persistence.migrations.v1_to_v2 import migrate_v1_to_v2

__all__ = ["migrate_v1_to_v2"]
