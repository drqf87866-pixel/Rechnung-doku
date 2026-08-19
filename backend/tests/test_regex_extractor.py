from __future__ import annotations

from app.services.regex_extractor import extract_invoice_data, parse_german_number


def test_deutsches_beispiel():
    text = "Rechnungsnummer: RE-2024-0157\nRechnungsbetrag: 1.234,56 EUR"
    result = extract_invoice_data(text)
    assert result.rechnungsnummer == "RE-2024-0157"
    assert result.rechnungsbetrag == 1234.56
    assert result.waehrung == "EUR"
    assert result.konfidenz == 1.0
    assert result.hinweise is None


def test_englischer_betrag_usd():
    text = "Invoice total: 1250.00 USD"
    result = extract_invoice_data(text)
    assert result.rechnungsbetrag == 1250.0


def test_keine_rechnungsnummer():
    text = "Betrag: 99,90 €"
    result = extract_invoice_data(text)
    assert result.rechnungsnummer is None
    assert result.rechnungsbetrag == 99.9
    assert result.konfidenz == 0.6
    assert result.hinweise is not None
    assert "Keine Rechnungsnummer gefunden" in result.hinweise


def test_nur_betrag_mit_euro_symbol():
    text = "Summe: 12,50 €"
    result = extract_invoice_data(text)
    assert result.rechnungsbetrag == 12.5
    assert result.waehrung == "EUR"
    assert result.rechnungsnummer is None


def test_chf_waehrung():
    text = "Gesamtbetrag: 2500.00 CHF"
    result = extract_invoice_data(text)
    assert result.rechnungsbetrag == 2500.0
    assert result.waehrung == "CHF"


def test_rechnungsnummer_code_muster():
    text = "Kundennummer: 4711\nRG 12345 Gesamtbetrag: 500,00 €"
    result = extract_invoice_data(text)
    assert result.rechnungsnummer == "RG 12345"
    assert result.rechnungsbetrag == 500.0


def test_parse_german_number_faelle():
    assert parse_german_number("1.234,56") == 1234.56
    assert parse_german_number("1234,56") == 1234.56
    assert parse_german_number("1234.56") == 1234.56
    assert parse_german_number("1 234,56") == 1234.56
