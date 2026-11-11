import hashlib
import os
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from typing import Protocol

from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from pypdf import PdfReader
from pypdf.errors import PdfReadError

MAX_POLICY_FILE_SIZE = 10 * 1024 * 1024
ALLOWED_POLICY_EXTENSIONS = {".md", ".pdf", ".txt"}
COLLECTION_NAME = "leave_policies"


class PolicyVectorStore(Protocol):
    def add_documents(
        self,
        documents: list[Document],
        ids: list[str] | None = None,
    ) -> list[str]: ...

    def get(self, **kwargs: object) -> dict[str, list[str]]: ...

    def delete(
        self,
        ids: list[str] | None = None,
        **kwargs: object,
    ) -> None: ...

    def similarity_search(
        self,
        query: str,
        k: int = 4,
        **kwargs: object,
    ) -> list[Document]: ...


def _vector_store_directory() -> str:
    configured_directory = os.getenv("LEAVE_POLICY_VECTOR_STORE_DIR")
    if configured_directory:
        return configured_directory
    return str(Path(__file__).resolve().parents[1] / "rags" / "chroma_db")


@lru_cache(maxsize=1)
def get_leave_policy_vector_store() -> Chroma:
    embedding_model = os.getenv(
        "LEAVE_POLICY_EMBEDDING_MODEL",
        "sentence-transformers/all-MiniLM-L6-v2",
    )
    embeddings = HuggingFaceEmbeddings(model_name=embedding_model)
    return Chroma(
        collection_name=COLLECTION_NAME,
        persist_directory=_vector_store_directory(),
        embedding_function=embeddings,
    )


def _policy_document_text(
    file_name: str,
    content: bytes,
) -> list[Document]:
    extension = Path(file_name).suffix.lower()
    if extension not in ALLOWED_POLICY_EXTENSIONS:
        raise ValueError("Only PDF, Markdown, and plain-text policy files are supported.")
    if not content:
        raise ValueError("Policy file is empty.")
    if len(content) > MAX_POLICY_FILE_SIZE:
        raise ValueError("Policy file exceeds the 10 MB upload limit.")

    if extension == ".pdf":
        try:
            reader = PdfReader(BytesIO(content))
        except PdfReadError as exc:
            raise ValueError("The uploaded PDF could not be read.") from exc
        documents = [
            Document(
                page_content=page.extract_text() or "",
                metadata={"source": file_name, "page": page_number},
            )
            for page_number, page in enumerate(reader.pages, start=1)
        ]
    else:
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ValueError("Policy text files must use UTF-8 encoding.") from exc
        documents = [
            Document(
                page_content=text,
                metadata={"source": file_name},
            )
        ]

    if not any(document.page_content.strip() for document in documents):
        raise ValueError("No searchable text was found in the policy file.")
    return [document for document in documents if document.page_content.strip()]


def _policy_chunks(file_name: str, content: bytes) -> list[Document]:
    source_documents = _policy_document_text(file_name, content)
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=150,
        add_start_index=True,
    )
    chunks = splitter.split_documents(source_documents)
    for chunk in chunks:
        chunk.metadata["source"] = file_name
    return chunks


def index_leave_policy(
    file_name: str,
    content: bytes,
    vector_store: PolicyVectorStore | None = None,
) -> int:
    safe_file_name = Path(file_name.replace("\\", "/")).name
    if not safe_file_name:
        raise ValueError("Policy filename is required.")

    chunks = _policy_chunks(safe_file_name, content)
    store = vector_store or get_leave_policy_vector_store()
    existing = store.get(where={"source": safe_file_name})
    existing_ids = set(existing.get("ids", []))

    new_ids = [
        hashlib.sha256(
            f"{safe_file_name}:{index}".encode("utf-8")
        ).hexdigest()
        for index in range(len(chunks))
    ]
    store.add_documents(chunks, ids=new_ids)

    stale_ids = existing_ids - set(new_ids)
    if stale_ids:
        store.delete(ids=sorted(stale_ids))
    return len(chunks)


def search_leave_policies(
    query: str,
    *,
    vector_store: PolicyVectorStore | None = None,
    limit: int = 4,
) -> list[dict[str, str | int]]:
    if not query.strip():
        raise ValueError("Policy search query cannot be empty.")
    if limit < 1 or limit > 10:
        raise ValueError("Policy search result limit must be between 1 and 10.")

    store = vector_store or get_leave_policy_vector_store()
    documents = store.similarity_search(query.strip(), k=limit)
    return [
        {
            "source": str(document.metadata.get("source", "Unknown policy")),
            "page": int(document.metadata["page"])
            if document.metadata.get("page") is not None
            else "",
            "content": document.page_content,
        }
        for document in documents
        if document.page_content.strip()
    ]
