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
    # Text so, wie er aus einem typischen Scan stammen könnte (Regex-Pfad).
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


def test_dockenhudener_layout():
    """Rechnung / Nummer / Wert + Endbetrag (Friedrich Lange)."""
    text = (
        "Rechnung\n"
        "Nummer\n"
        "91016032\n"
        "Datum\n"
        "17.08.2026\n"
        "Kundennummer\n"
        "1020558\n"
        "Endbetrag\n"
        "24,15\n"
        "Bis zum 27.08.2026 erhalten Sie 2,000  % Skonto\n"
    )
    result = extract_invoice_data(text)
    assert result.rechnungsnummer == "91016032"
    assert result.rechnungsbetrag == 24.15
    assert result.konfidenz == 1.0


def test_kdw_layout_kein_datumsbetrag():
    """Endbetrag vor Zahlbetrag-Skonto; Datum 02.09.2026 nicht als Betrag."""
    text = (
        "Aktion MA Trennscheibe INOX 125x1,0mm\n"
        "Endbetrag\n"
        "       30,29  EUR\n"
        "Zahlbetrag bis 02.09.2026 3,000 % Skonto\n"
        "               29,40  EUR\n"
        "Zahlbetrag bis 18.09.2026 ohne Abzug\n"
        "               30,29  EUR\n"
        "Rechnung\n"
        "Datum\n"
        "Seite\n"
        "407614216\n"
        "19.08.2026\n"
        "1  /  1\n"
    )
    result = extract_invoice_data(text)
    assert result.rechnungsnummer == "407614216"
    assert result.rechnungsbetrag == 30.29
    assert result.rechnungsbetrag != 2.09


def test_bogdanski_tabellenkopf():
    """KD-Nr. kann mehrteilig sein (926 L02634); Rechn.Nr. steht vor Datum."""
    text = (
        "R E C H N U N G\n"
        "KD-Nr. Rechn.Nr.   Datum    Blatt\n"
        "926 L02634   878234\n"
        "13.08.2026  1\n"
        "AUFTR.NR. : Scholtz\n"
        "    Gesamt:      267,19 EUR\n"
    )
    result = extract_invoice_data(text)
    assert result.rechnungsnummer == "878234"
    assert result.rechnungsbetrag == 267.19


def test_bogdanski_werte_in_einer_zeile():
    """Wie im Scan: KD-Nr. '926 L02634', Rechn.Nr. '878234' vor Datum."""
    text = (
        "R E C H N U N G\n"
        "Bei Schriftwechsel bitte angeben\n"
        "KD-Nr. Rechn.Nr.    Datum        Blatt\n"
        "926 L02634      878234   13.08.2026   1\n"
        "    Gesamt:      267,19 EUR\n"
    )
    result = extract_invoice_data(text)
    assert result.rechnungsnummer == "878234"
    assert result.rechnungsbetrag == 267.19
    assert result.rechnungsnummer != "L02634"

def test_trennscheibe_kein_rechnungsnummer_fehltreffer():
    text = (
        "Makita Trennscheibe INOX 125x1,0 mm\n"
        "Zur Position gehören die Unterpositionen\n"
        "Endbetrag\n"
        "30,29 EUR\n"
    )
    result = extract_invoice_data(text)
    assert result.rechnungsnummer is None
    assert result.rechnungsbetrag == 30.29


def test_netto_und_steuer_explizit():
    text = (
        "Rechnungsnummer: RE-2024-100\n"
        "Nettobetrag: 100,00 EUR\n"
        "MwSt. 19%: 19,00 EUR\n"
        "Bruttobetrag: 119,00 EUR\n"
    )
    result = extract_invoice_data(text)
    assert result.rechnungsnummer == "RE-2024-100"
    assert result.rechnungsbetrag == 119.0
    assert result.nettobetrag == 100.0
    assert result.steuerbetrag == 19.0


def test_steuer_aus_brutto_und_netto_abgeleitet():
    text = (
        "Rechnungsnummer: RE-50\n"
        "Nettobetrag: 1.000,00 EUR\n"
        "Gesamtbetrag: 1.190,00 EUR\n"
    )
    result = extract_invoice_data(text)
    assert result.rechnungsbetrag == 1190.0
    assert result.nettobetrag == 1000.0
    assert result.steuerbetrag == 190.0


def test_netto_aus_brutto_und_steuer_abgeleitet():
    text = (
        "Rechnungsnummer: RE-51\n"
        "USt. 19%: 38,00 EUR\n"
        "Rechnungsbetrag: 238,00 EUR\n"
    )
    result = extract_invoice_data(text)
    assert result.rechnungsbetrag == 238.0
    assert result.steuerbetrag == 38.0
    assert result.nettobetrag == 200.0


def test_ohne_netto_steuer_bleiben_leer():
    text = "Rechnungsnummer: RE-52\nRechnungsbetrag: 50,00 EUR"
    result = extract_invoice_data(text)
    assert result.rechnungsbetrag == 50.0
    assert result.nettobetrag is None
    assert result.steuerbetrag is None


def test_spaltenlayout_kundennummer_links_nicht_als_rechnung():
    """Header Kundennummer | Rechnungsnummer → zweite Spalte."""
    text = (
        "Kundennummer    Rechnungsnummer\n"
        "1020558         91016032\n"
        "Endbetrag 24,15 EUR\n"
    )
    result = extract_invoice_data(text)
    assert result.rechnungsnummer == "91016032"
    assert result.rechnungsbetrag == 24.15


def test_spaltenlayout_rechnungsnummer_links():
    text = (
        "Rechnungsnummer    Kundennummer\n"
        "91016032           1020558\n"
        "Endbetrag 24,15 EUR\n"
    )
    result = extract_invoice_data(text)
    assert result.rechnungsnummer == "91016032"
    assert result.rechnungsbetrag == 24.15


def test_slash_header_kunden_vor_rechnung():
    text = (
        "Kundennummer / Rechnungsnummer\n"
        "1020558 / 91016032\n"
        "Gesamtbetrag: 99,00 €\n"
    )
    result = extract_invoice_data(text)
    assert result.rechnungsnummer == "91016032"
    assert result.rechnungsbetrag == 99.0


def test_kd_nr_slash_rechn_nr():
    text = (
        "Kd.-Nr. / Rechn.-Nr.\n"
        "4711 / RE-2024-1\n"
        "Rechnungsbetrag: 10,00 €\n"
    )
    result = extract_invoice_data(text)
    assert result.rechnungsnummer == "RE-2024-1"
    assert result.rechnungsbetrag == 10.0


def test_nur_kundennummer_keine_rechnungsnummer():
    text = "Kundennummer: 1020558\nEndbetrag: 24,15 EUR"
    result = extract_invoice_data(text)
    assert result.rechnungsnummer is None
    assert result.rechnungsbetrag == 24.15


def test_kundennummer_und_rechnungsnummer_getrennt_gelabelt():
    text = (
        "Ihre Kundennummer: 1020558\n"
        "Rechnungsnummer: 91016032\n"
        "Endbetrag: 24,15\n"
    )
    result = extract_invoice_data(text)
    assert result.rechnungsnummer == "91016032"
    assert result.rechnungsbetrag == 24.15
