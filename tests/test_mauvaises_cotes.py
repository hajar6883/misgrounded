"""Le banc des mauvaises cotes : seule la cote change, et le leurre est propre.

Si une piece leurre se mettait a reprendre le fait, le deplacement ne serait
plus une erreur et le rappel mesure serait faux, sans bruit. D'ou les gardes.
"""

from __future__ import annotations

import json

import pytest

from controle_pieces import mauvaises_cotes as mc
from controle_pieces.checks import controler
from controle_pieces.chemins import ACTE_COTES, ACTE_LLM, COTES_DEPLACEES
from controle_pieces.dossier import par_cote
from controle_pieces.extract import extraire


@pytest.fixture(scope="module")
def sain():
    return extraire(ACTE_LLM.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def modifie():
    return extraire(ACTE_COTES.read_text(encoding="utf-8"))


def test_chaque_ancrage_apparait_exactement_une_fois():
    acte = ACTE_LLM.read_text(encoding="utf-8")
    for d in mc.DEPLACEMENTS:
        assert acte.count(d.avant) == 1, d.erreur_id


def test_seule_la_citation_change():
    for d in mc.DEPLACEMENTS:
        assert d.cote_leurre != d.cote_correcte, d.erreur_id
        assert mc.CITATION.sub("", d.avant) == mc.CITATION.sub("", d.apres), d.erreur_id
        assert f"(pièce n° {d.cote_correcte}" in d.avant, d.erreur_id


def test_les_affirmations_sont_celles_de_l_acte_sain(sain, modifie):
    """Meme decoupage, meme texte : la passe A juge exactement la meme chose."""
    assert [(a.claim_id, a.texte, a.valeur_brute) for a in sain] == [
        (a.claim_id, a.texte, a.valeur_brute) for a in modifie
    ]


def test_seuls_les_segments_deplaces_changent_de_cote(sain, modifie):
    for a, b in zip(sain, modifie):
        d = mc.deplacement_du_segment(b.debut, b.fin)
        if d is None:
            assert a.cote_citee == b.cote_citee, b.claim_id
        else:
            assert (a.cote_citee, b.cote_citee) == (d.cote_correcte, d.cote_leurre), b.claim_id


def test_chaque_deplacement_touche_au_moins_une_affirmation(modifie):
    touches = {
        d.erreur_id
        for b in modifie
        if (d := mc.deplacement_du_segment(b.debut, b.fin)) is not None
    }
    assert touches == {d.erreur_id for d in mc.DEPLACEMENTS}


def test_le_leurre_ne_confirme_aucune_valeur_deplacee(modifie):
    """La garde essentielle : la piece leurre ne doit pas soutenir le fait."""
    pieces = par_cote()
    for b in modifie:
        d = mc.deplacement_du_segment(b.debut, b.fin)
        if d is None or b.valeur is None:
            continue
        verdict = controler(b.valeur, pieces[d.cote_leurre].texte).verdict
        assert verdict != "confirme", f"{d.erreur_id} / {b.claim_id} : {b.valeur_brute}"


def test_la_construction_est_reproductible():
    reconstruit, deplacements = mc.construire(ecrire=False)
    assert reconstruit == ACTE_COTES.read_text(encoding="utf-8")
    journal = json.loads(COTES_DEPLACEES.read_text(encoding="utf-8"))
    assert journal["deplacements"] == deplacements
