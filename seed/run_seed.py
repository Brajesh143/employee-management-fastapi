import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from database import SessionLocal
from seed.permissions import seed_permissions
from seed.role_permissions import seed_role_permissions


def run():
    db = SessionLocal()

    try:
        seed_permissions(db)
        seed_role_permissions(db)

    finally:
        db.close()


if __name__ == "__main__":
    run()