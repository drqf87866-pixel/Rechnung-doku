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


def test_parse_german_number_tausender_ohne_dezimal():
    assert parse_german_number("1.234") == 1234.0
    assert parse_german_number("2500.00") == 2500.0


def test_ocr_scan_typisch():
    # Text so, wie ihn RapidOCR aus dem Beispiel-Scan liefert.
    text = (
        "Orthopädische Gemeinschaftspraxis\n"
        "Re. - Nr. 100984\n"
        "Patient: Peters, Maximilian\n"
        "Rechnungsbetrag\n"
        "30,83 EUR\n"
        "zuzgl. Mahngebühr\n"
        "0,00 EUR\n"
        "Offener Restbetrag\n"
        "30,83 EUR\n"
    )
    result = extract_invoice_data(text)
    assert result.rechnungsnummer == "100984"
    assert result.rechnungsbetrag == 30.83
    assert result.waehrung == "EUR"
    assert result.konfidenz == 1.0
    assert result.hinweise is None


def test_rechnungsnummer_auf_naechster_zeile():
    text = "Rechnungsnummer:\nRE-2024-0157\nRechnungsbetrag: 1.234,56 EUR"
    result = extract_invoice_data(text)
    assert result.rechnungsnummer == "RE-2024-0157"
    assert result.rechnungsbetrag == 1234.56


def test_rechnungsnummer_schreibweisen():
    for label in [
        "Rechnungs-Nr.",
        "Re.-Nr.",
        "Rg.-Nr.",
        "Rechnung Nr.",
        "Rechnungsnr.",
        "Invoice No.",
    ]:
        text = f"{label}: 2024-0157\nRechnungsbetrag: 500,00 €"
        result = extract_invoice_data(text)
        assert result.rechnungsnummer == "2024-0157", label


def test_rechnung_ohne_nr_kein_fehltreffer():
    text = "Rechnung vom 27.05.26\nKundennummer: 4711\nRechnungsbetrag: 99,90 €"
    result = extract_invoice_data(text)
    assert result.rechnungsnummer is None
    assert result.rechnungsbetrag == 99.9


def test_betrag_ohne_nachkommastellen():
    text = "Rechnungsnummer: RE-1\nRechnungsbetrag: 500 €"
    result = extract_invoice_data(text)
    assert result.rechnungsbetrag == 500.0


def test_betrag_mit_tausenderpunkt_ohne_dezimal():
    text = "Rechnungsnummer: RE-2\nSumme: 1.234 €"
    result = extract_invoice_data(text)
    assert result.rechnungsbetrag == 1234.0


def test_zu_zahlen_tage_kein_fehltreffer():
    text = "Rechnungsnummer: RE-3\nZahlungsziel: 30 Tage\nZu zahlen 30 Tage"
    result = extract_invoice_data(text)
    assert result.rechnungsbetrag is None


def test_waehrung_vor_betrag():
    text = "Rechnungsnummer: RE-4\nGesamt: € 45,00"
    result = extract_invoice_data(text)
    assert result.rechnungsbetrag == 45.0
