from __future__ import annotations

import fitz

from app.services.invoice_extractor import extract_from_pdf
from app.services.llm_extractor import LlmInvoiceFields
from app.services.regex_extractor import ExtractionResult


def test_extract_from_pdf_digital_uses_regex():
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "Rechnungsnummer: RE-2024-0157\nRechnungsbetrag: 1.234,56 EUR")
    data = document.tobytes()
    document.close()

    result = extract_from_pdf(data)
    assert result.rechnungsnummer == "RE-2024-0157"
    assert result.rechnungsbetrag == 1234.56
    assert result.konfidenz == 1.0


def test_extract_from_pdf_scan_without_api_key(monkeypatch):
    document = fitz.open()
    document.new_page()
    data = document.tobytes()
    document.close()

    monkeypatch.setattr("app.services.llm_extractor.settings.gemini_api_key", None)

    result = extract_from_pdf(data)
    assert result.rechnungsnummer is None
    assert result.rechnungsbetrag is None
    assert result.konfidenz == 0.0
    assert "GEMINI_API_KEY" in (result.hinweise or "")


def test_extract_from_pdf_scan_uses_llm(monkeypatch):
    document = fitz.open()
    document.new_page()
    data = document.tobytes()
    document.close()

    monkeypatch.setattr("app.services.llm_extractor.settings.gemini_api_key", "test-key")

    def fake_llm(_pdf_bytes: bytes, text: str | None = None) -> ExtractionResult:
        return ExtractionResult(
            rechnungsnummer="100984",
            rechnungsbetrag=30.83,
            waehrung="EUR",
            konfidenz=0.9,
            hinweise="Per Gemini extrahiert",
        )

    monkeypatch.setattr(
        "app.services.invoice_extractor.extract_invoice_data_via_llm",
        fake_llm,
    )

    result = extract_from_pdf(data)
    assert result.rechnungsnummer == "100984"
    assert result.rechnungsbetrag == 30.83


def test_extract_from_pdf_incomplete_regex_falls_back_to_llm(monkeypatch):
    """Digitale PDF mit Text, aber ohne erkennbare Nummer → Gemini-Fallback."""
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "Nur ein Betrag ohne Nummer\nGesamtbetrag: 99,90 EUR")
    data = document.tobytes()
    document.close()

    monkeypatch.setattr("app.services.invoice_extractor.settings.gemini_api_key", "test-key")
    called = {"llm": False}

    def fake_llm(_pdf_bytes: bytes, text: str | None = None) -> ExtractionResult:
        called["llm"] = True
        return ExtractionResult(
            rechnungsnummer="FALLBACK-1",
            rechnungsbetrag=99.9,
            waehrung="EUR",
            konfidenz=0.9,
            hinweise="Per Gemini extrahiert",
        )

    monkeypatch.setattr(
        "app.services.invoice_extractor.extract_invoice_data_via_llm",
        fake_llm,
    )

    result = extract_from_pdf(data)
    assert called["llm"] is True
    assert result.rechnungsnummer == "FALLBACK-1"
    assert result.rechnungsbetrag == 99.9


def test_extract_from_pdf_digital_reconciles_winner_takes_all(monkeypatch):
    """Regex hat beide Felder gefunden (aber falschen Betrag), Gemini korrigiert mit Arithmetik."""
    document = fitz.open()
    page = document.new_page()
    # Regex findet ggf. Summe: 10,00 EUR
    page.insert_text(
        (72, 72),
        "Rechnungsnummer: RE-2024-999\nSumme: 10,00 EUR\nEndbetrag: 119,00 EUR",
    )
    data = document.tobytes()
    document.close()

    monkeypatch.setattr("app.services.invoice_extractor.settings.gemini_api_key", "test-key")

    def fake_llm(_pdf_bytes: bytes, text: str | None = None) -> ExtractionResult:
        return ExtractionResult(
            rechnungsnummer="RE-2024-999",
            rechnungsbetrag=119.0,
            nettobetrag=100.0,
            steuerbetrag=19.0,
            waehrung="EUR",
            konfidenz=0.9,
            hinweise="Per Gemini extrahiert",
        )

    monkeypatch.setattr(
        "app.services.invoice_extractor.extract_invoice_data_via_llm",
        fake_llm,
    )

    result = extract_from_pdf(data)
    assert result.rechnungsnummer == "RE-2024-999"
    assert result.rechnungsbetrag == 119.0
    assert result.nettobetrag == 100.0
    assert result.steuerbetrag == 19.0


def test_extract_from_pdf_merges_missing_fields(monkeypatch):
    """Regex findet Nummer, Gemini findet Betrag → Felder werden zusammengeführt."""
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "Rechnungsnummer: RE-MERGE-42\nKein Betrag hier")
    data = document.tobytes()
    document.close()

    monkeypatch.setattr("app.services.invoice_extractor.settings.gemini_api_key", "test-key")

    def fake_llm(_pdf_bytes: bytes, text: str | None = None) -> ExtractionResult:
        return ExtractionResult(
            rechnungsnummer=None,
            rechnungsbetrag=250.0,
            waehrung="EUR",
            konfidenz=0.6,
            hinweise=None,
        )

    monkeypatch.setattr(
        "app.services.invoice_extractor.extract_invoice_data_via_llm",
        fake_llm,
    )

    result = extract_from_pdf(data)
    assert result.rechnungsnummer == "RE-MERGE-42"
    assert result.rechnungsbetrag == 250.0
    assert result.konfidenz == 0.9


def test_extract_from_pdf_agreement_gives_high_confidence(monkeypatch):
    """Wenn Regex und Gemini übereinstimmen, ist Konfidenz 1.0 ohne Konflikthinweis."""
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "Rechnungsnummer: RE-AGREE-2024\nGesamtbetrag: 500,00 EUR")
    data = document.tobytes()
    document.close()

    monkeypatch.setattr("app.services.invoice_extractor.settings.gemini_api_key", "test-key")

    def fake_llm(_pdf_bytes: bytes, text: str | None = None) -> ExtractionResult:
        return ExtractionResult(
            rechnungsnummer="RE-AGREE-2024",
            rechnungsbetrag=500.0,
            waehrung="EUR",
            konfidenz=0.9,
            hinweise=None,
        )

    monkeypatch.setattr(
        "app.services.invoice_extractor.extract_invoice_data_via_llm",
        fake_llm,
    )

    result = extract_from_pdf(data)
    assert result.rechnungsnummer == "RE-AGREE-2024"
    assert result.rechnungsbetrag == 500.0
    assert result.konfidenz == 1.0
    assert result.hinweise is None


def test_extract_from_pdf_discrepancy_signals_conflict(monkeypatch):
    """Widerspruch ohne Arithmetik-Klarheit senkt Konfidenz und hinterlässt Hinweis."""
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "Rechnungsnummer: RE-111\nGesamtbetrag: 100,00 EUR")
    data = document.tobytes()
    document.close()

    monkeypatch.setattr("app.services.invoice_extractor.settings.gemini_api_key", "test-key")

    def fake_llm(_pdf_bytes: bytes, text: str | None = None) -> ExtractionResult:
        return ExtractionResult(
            rechnungsnummer="RE-222",
            rechnungsbetrag=200.0,
            waehrung="EUR",
            konfidenz=0.9,
            hinweise=None,
        )

    monkeypatch.setattr(
        "app.services.invoice_extractor.extract_invoice_data_via_llm",
        fake_llm,
    )

    result = extract_from_pdf(data)
    assert result.konfidenz == 0.6
    assert result.hinweise is not None
    assert "Konflikt" in result.hinweise or "gewählt" in result.hinweise


def test_extract_from_pdf_passes_text_to_llm(monkeypatch):
    """Prüft, ob der aus PyMuPDF extrahierte Text an extract_invoice_data_via_llm übergeben wird."""
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "Rechnung mit speziellem Text für LLM")
    data = document.tobytes()
    document.close()

    monkeypatch.setattr("app.services.invoice_extractor.settings.gemini_api_key", "test-key")
    received_text = {"text": None}

    def fake_llm(_pdf_bytes: bytes, text: str | None = None) -> ExtractionResult:
        received_text["text"] = text
        return ExtractionResult(
            rechnungsnummer="RE-LLM",
            rechnungsbetrag=10.0,
            waehrung="EUR",
            konfidenz=0.9,
            hinweise=None,
        )

    monkeypatch.setattr(
        "app.services.invoice_extractor.extract_invoice_data_via_llm",
        fake_llm,
    )

    extract_from_pdf(data)
    assert received_text["text"] is not None
    assert "Rechnung mit speziellem Text" in received_text["text"]


def test_llm_result_from_fields():
    from app.services.llm_extractor import _result_from_fields

    result = _result_from_fields(
        LlmInvoiceFields(
            rechnungsnummer="RE-99",
            rechnungsbetrag=42.5,
            waehrung="EUR",
        )
    )
    assert result.rechnungsnummer == "RE-99"
    assert result.rechnungsbetrag == 42.5
    assert result.nettobetrag is None
    assert result.steuerbetrag is None
    assert result.konfidenz == 0.9


def test_llm_result_from_fields_with_netto_steuer():
    from app.services.llm_extractor import _result_from_fields

    result = _result_from_fields(
        LlmInvoiceFields(
            rechnungsnummer="RE-100",
            rechnungsbetrag=119.0,
            nettobetrag=100.0,
            steuerbetrag=19.0,
            waehrung="EUR",
        )
    )
    assert result.rechnungsbetrag == 119.0
    assert result.nettobetrag == 100.0
    assert result.steuerbetrag == 19.0


def test_llm_result_derives_steuer():
    from app.services.llm_extractor import _result_from_fields

    result = _result_from_fields(
        LlmInvoiceFields(
            rechnungsnummer="RE-101",
            rechnungsbetrag=119.0,
            nettobetrag=100.0,
            waehrung="EUR",
        )
    )
    assert result.steuerbetrag == 19.0


def test_llm_verwirft_kundennummer_als_rechnungsnummer():
    from app.services.llm_extractor import _result_from_fields

    result = _result_from_fields(
        LlmInvoiceFields(
            kundennummer="1020558",
            rechnungsnummer="1020558",
            rechnungsbetrag=24.15,
            waehrung="EUR",
        )
    )
    assert result.rechnungsnummer is None
    assert result.rechnungsbetrag == 24.15
    assert "Keine Rechnungsnummer gefunden" in (result.hinweise or "")


def test_llm_verwirft_teil_der_mehrteiligen_kundennummer():
    from app.services.llm_extractor import _result_from_fields

    result = _result_from_fields(
        LlmInvoiceFields(
            kundennummer="926 L02634",
            rechnungsnummer="L02634",
            rechnungsbetrag=267.19,
            waehrung="EUR",
        )
    )
    assert result.rechnungsnummer is None
    assert result.rechnungsbetrag == 267.19


def test_llm_behaelt_echte_rechnungsnummer_neben_kundennummer():
    from app.services.llm_extractor import _result_from_fields

    result = _result_from_fields(
        LlmInvoiceFields(
            kundennummer="1020558",
            rechnungsnummer="91016032",
            rechnungsbetrag=24.15,
            waehrung="EUR",
        )
    )
    assert result.rechnungsnummer == "91016032"
    assert result.rechnungsbetrag == 24.15
    assert result.konfidenz == 0.9


def test_llm_bogdanski_rechn_nr_neben_mehrteiliger_kd_nr():
    from app.services.llm_extractor import _result_from_fields

    result = _result_from_fields(
        LlmInvoiceFields(
            kundennummer="926 L02634",
            rechnungsnummer="878234",
            rechnungsbetrag=267.19,
            waehrung="EUR",
        )
    )
    assert result.rechnungsnummer == "878234"
    assert result.konfidenz == 0.9


def test_llm_verwirft_jahr_und_bemessungsgrundlage():
    from app.services.llm_extractor import _result_from_fields

    result = _result_from_fields(
        LlmInvoiceFields(
            rechnungsnummer="91016032",
            rechnungsbetrag=24.15,
            nettobetrag=2026.0,
            steuerbetrag=20.29,
            waehrung="EUR",
        )
    )
    assert result.rechnungsbetrag == 24.15
    assert result.nettobetrag != 2026
    assert result.steuerbetrag != 20.29
