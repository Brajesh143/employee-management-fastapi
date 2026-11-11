from io import BytesIO
from types import SimpleNamespace

import pytest

from services import ai_document_processing


class FakePage:
    def __init__(self, text: str):
        self.text = text

    def extract_text(self) -> str:
        return self.text


class FakeStorage:
    def open(self, storage_key: str):
        assert storage_key == "employees/1/offer.pdf"
        return BytesIO(b"%PDF-1.7")


class FakeLLM:
    def __init__(self, content: str):
        self.content = content
        self.messages = None

    def invoke(self, messages):
        self.messages = messages
        return SimpleNamespace(content=self.content)


def _pdf_reader_with_text(text: str):
    class FakePdfReader:
        def __init__(self, content: BytesIO):
            assert content.read() == b"%PDF-1.7"
            self.pages = [FakePage(text)]

    return FakePdfReader


def _document(content_type: str = "application/pdf"):
    return SimpleNamespace(
        id=17,
        file_name="offer.pdf",
        content_type=content_type,
        storage_key="employees/1/offer.pdf",
    )


def test_analyze_employee_document_classifies_and_summarizes_pdf(
    monkeypatch,
):
    monkeypatch.setattr(
        ai_document_processing,
        "PdfReader",
        _pdf_reader_with_text("Offer of employment for employee 17."),
    )
    llm = FakeLLM(
        "Document type: Offer letter\nSummary: Employment offer details."
    )

    result = ai_document_processing.analyze_employee_document(
        _document(),
        FakeStorage(),
        llm=llm,
    )

    assert result.document_id == 17
    assert result.file_name == "offer.pdf"
    assert result.analysis.startswith("Document type: Offer letter")
    assert result.source_text_truncated is False
    assert "Offer of employment" in llm.messages[1].content
    assert "untrusted data" in llm.messages[0].content


def test_analyze_employee_document_truncates_long_source_text(
    monkeypatch,
):
    monkeypatch.setattr(
        ai_document_processing,
        "MAX_ANALYSIS_TEXT_LENGTH",
        20,
    )
    monkeypatch.setattr(
        ai_document_processing,
        "PdfReader",
        _pdf_reader_with_text("A" * 100),
    )
    llm = FakeLLM("Document type: Other\nSummary: Short summary.")

    result = ai_document_processing.analyze_employee_document(
        _document(),
        FakeStorage(),
        llm=llm,
    )

    assert result.source_text_truncated is True
    analyzed_text = llm.messages[1].content.split("<document>\n", 1)[1].split(
        "\n</document>", 1
    )[0]
    assert len(analyzed_text) == 20


def test_analyze_employee_document_rejects_non_pdf():
    with pytest.raises(ValueError, match="PDF documents only"):
        ai_document_processing.analyze_employee_document(
            _document("image/png"),
            FakeStorage(),
            llm=FakeLLM("unused"),
        )


def test_analyze_employee_document_rejects_pdf_without_searchable_text(
    monkeypatch,
):
    monkeypatch.setattr(
        ai_document_processing,
        "PdfReader",
        _pdf_reader_with_text(" \n"),
    )

    with pytest.raises(ValueError, match="no searchable text"):
        ai_document_processing.analyze_employee_document(
            _document(),
            FakeStorage(),
            llm=FakeLLM("unused"),
        )
