"""Les resumes du bordereau, troisieme surface de verification.

Un modele qui a la piece sous les yeux et avance des chiffres : le cas le plus
favorable qui soit. Ces tests tournent hors ligne.
"""

from __future__ import annotations

import re

import pytest

from controle_pieces.dossier import charger_bordereau
from controle_pieces.resumes import controler_resume, controler_tous


@pytest.fixture(scope="module")
def controles():
    return controler_tous()


def test_chaque_piece_porte_un_titre_date():
    """Format du bordereau : le titre doit contenir la date de la piece."""
    for p in charger_bordereau():
        assert p.titre, f"{p.doc_id} : titre manquant"
        assert re.search(r"\d{2}/\d{2}/\d{4}", p.titre), (
            f"{p.doc_id} : le titre ne porte pas de date — {p.titre!r}"
        )


def test_chaque_piece_porte_un_resume(controles):
    assert len(controles) == 10


def test_les_resumes_font_deux_a_trois_lignes():
    """Le format impose la concision : on tolere 20 a 70 mots."""
    for p in charger_bordereau():
        mots = len(p.resume.split())
        assert 20 <= mots <= 70, f"{p.doc_id} : {mots} mots"


def test_les_resumes_sont_charges_de_chiffres(controles):
    """Un resume de bordereau sans chiffre ne sert a rien."""
    for c in controles:
        assert c.valeurs >= 1, f"{c.doc_id} : aucune valeur chiffree"


def test_aucun_resume_ne_contredit_sa_propre_piece(controles):
    """La garantie mesuree : 0 contradiction sur 38 valeurs."""
    fautifs = {c.doc_id: c.contredites for c in controles if not c.fiable}
    assert not fautifs, fautifs


def test_la_grande_majorite_des_valeurs_est_confirmee(controles):
    total = sum(c.valeurs for c in controles)
    confirmees = sum(c.confirmees for c in controles)
    assert total >= 30
    assert confirmees / total >= 0.9


def test_un_resume_falsifie_est_bien_detecte():
    """Contre-epreuve : si le controle ne detectait rien, il ne prouverait rien."""
    piece = next(p for p in charger_bordereau() if p.cote == 6)
    faux = "Facture n° F-2024-0731 du 21 novembre 2024 pour 88 888,00 € HT."
    controle = controler_resume(piece, faux)
    assert not controle.fiable
    assert any("88 888" in c for c in controle.contredites)


def test_un_resume_qui_inverse_ht_et_ttc_est_detecte():
    piece = next(p for p in charger_bordereau() if p.cote == 6)
    faux = "Facture n° F-2024-0731 du 21 novembre 2024 pour 59 200,00 € TTC."
    controle = controler_resume(piece, faux)
    assert not controle.fiable
    assert any("TTC" in c for c in controle.contredites)
