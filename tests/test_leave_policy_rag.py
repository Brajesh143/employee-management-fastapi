import pytest
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import main  # noqa: F401
from auth.dependencies import get_current_user
from database import get_db
from database.database import Base
from models.employee import Employee
from models.permission import Permission
from models.role import Role
from models.role_permission import RolePermission
from routers.ai_chat import router as ai_router
from services.leave_policy_rag import (
    MAX_POLICY_FILE_SIZE,
    index_leave_policy,
    search_leave_policies,
)


class FakePolicyVectorStore:
    def __init__(self):
        self.documents = {}
        self.deleted_ids = []

    def get(self, **kwargs):
        source = kwargs["where"]["source"]
        return {
            "ids": [
                document_id
                for document_id, document in self.documents.items()
                if document.metadata["source"] == source
            ]
        }

    def add_documents(self, documents, ids=None):
        for document, document_id in zip(documents, ids or []):
            self.documents[document_id] = document
        return ids or []

    def delete(self, ids=None, **_kwargs):
        for document_id in ids or []:
            self.deleted_ids.append(document_id)
            self.documents.pop(document_id, None)

    def similarity_search(self, query, k=4, **_kwargs):
        return list(self.documents.values())[:k]


def test_index_replaces_policy_chunks_and_search_returns_source():
    store = FakePolicyVectorStore()
    initial_count = index_leave_policy(
        "leave-policy.txt",
        b"Casual leave allowance is twelve days each year.",
        vector_store=store,
    )
    assert initial_count == 1

    updated_count = index_leave_policy(
        "leave-policy.txt",
        b"Casual leave allowance is twelve days each year. "
        b"Unused leave does not carry over. " * 100,
        vector_store=store,
    )
    assert updated_count > 1
    results = search_leave_policies(
        "Does unused leave carry over?",
        vector_store=store,
    )
    assert results
    assert all(result["source"] == "leave-policy.txt" for result in results)
    assert any("Unused leave does not carry over." in result["content"] for result in results)

    index_leave_policy(
        "leave-policy.txt",
        b"Casual leave allowance is twelve days each year.",
        vector_store=store,
    )
    assert store.deleted_ids


@pytest.mark.parametrize(
    ("file_name", "content", "message"),
    [
        ("policy.docx", b"text", "Only PDF"),
        ("policy.txt", b"", "empty"),
        ("policy.txt", b"x" * (MAX_POLICY_FILE_SIZE + 1), "10 MB"),
        ("policy.pdf", b"not a pdf", "could not be read"),
        ("policy.txt", b"\xff", "UTF-8"),
    ],
)
def test_policy_index_rejects_unsupported_or_invalid_files(
    file_name,
    content,
    message,
):
    with pytest.raises(ValueError, match=message):
        index_leave_policy(
            file_name,
            content,
            vector_store=FakePolicyVectorStore(),
        )


def test_policy_upload_requires_ai_admin_permission(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    with Session(engine) as db:
        role = Role(name="HR policy uploader")
        employee_role = Role(name="Policy upload denied")
        permission = Permission(name="ai:admin")
        db.add_all([role, employee_role, permission])
        db.flush()
        db.add(RolePermission(role_id=role.id, permission_id=permission.id))
        hr_user = Employee(
            employee_code="POL001",
            first_name="Policy",
            last_name="Admin",
            email="policy.admin@example.com",
            password_hash="",
            role_id=role.id,
        )
        db.add(hr_user)
        employee_user = Employee(
            employee_code="POL002",
            first_name="Regular",
            last_name="Employee",
            email="regular.employee@example.com",
            password_hash="",
            role_id=employee_role.id,
        )
        db.add(employee_user)
        db.commit()
        hr_user_id = hr_user.id
        role_id = role.id
        employee_user_id = employee_user.id
        employee_role_id = employee_role.id

    app = FastAPI()
    app.include_router(ai_router, prefix="/api/v1")

    def override_get_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    current_user = {
        "user": SimpleNamespace(
            id=hr_user_id,
            role_id=role_id,
            role=SimpleNamespace(name="HR policy uploader"),
        )
    }
    app.dependency_overrides[get_current_user] = lambda: current_user["user"]
    monkeypatch.setattr(
        "routers.ai_chat.index_leave_policy",
        lambda file_name, content: 3,
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/ai/leave-policies",
            files={"file": ("policy.txt", b"Casual leave policy")},
        )
        current_user["user"] = SimpleNamespace(
            id=employee_user_id,
            role_id=employee_role_id,
            role=SimpleNamespace(name="Policy upload denied"),
        )
        denied = client.post(
            "/api/v1/ai/leave-policies",
            files={"file": ("policy.txt", b"Casual leave policy")},
        )
    assert response.status_code == 200
    assert denied.status_code == 403
    assert response.json() == {
        "file_name": "policy.txt",
        "chunks_indexed": 3,
    }

    engine.dispose()
