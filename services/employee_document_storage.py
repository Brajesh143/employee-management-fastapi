import os
from pathlib import Path, PurePosixPath
from typing import BinaryIO, Protocol


class DocumentStorage(Protocol):
    def save(self, storage_key: str, content: bytes) -> None: ...

    def open(self, storage_key: str) -> BinaryIO: ...

    def delete(self, storage_key: str) -> None: ...


class LocalDiskDocumentStorage:
    def __init__(self, root: Path):
        self.root = root.resolve()

    def _path(self, storage_key: str) -> Path:
        relative_path = PurePosixPath(storage_key)
        if (
            not relative_path.parts
            or relative_path.is_absolute()
            or ".." in relative_path.parts
        ):
            raise ValueError("Invalid document storage key.")

        path = (self.root / Path(*relative_path.parts)).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError("Invalid document storage key.")
        return path

    def save(self, storage_key: str, content: bytes) -> None:
        path = self._path(storage_key)
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        descriptor = os.open(
            path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
        with os.fdopen(descriptor, "wb") as document_file:
            document_file.write(content)

    def open(self, storage_key: str) -> BinaryIO:
        return self._path(storage_key).open("rb")

    def delete(self, storage_key: str) -> None:
        self._path(storage_key).unlink()


def get_document_storage() -> DocumentStorage:
    configured_root = os.getenv("EMPLOYEE_DOCUMENTS_DIR")
    root = (
        Path(configured_root)
        if configured_root
        else Path(__file__).resolve().parents[1]
        / "local_storage"
        / "employee_documents"
    )
    return LocalDiskDocumentStorage(root)
