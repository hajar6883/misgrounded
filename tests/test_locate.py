"""Localisation : distinguer la mauvaise cote de l'hallucination.

Regle du module : ne prononcer que sur ce qui est decidable. Le reste est
renvoye au juge, et c'est ce qui garde la localisation sans fausse alerte.
"""

from __future__ import annotations

import json

import pytest

from controle_pieces.checks import controler
from controle_pieces.chemins import ACTE_LLM, ACTE_PIEGE, ERREURS_PLANTEES
from controle_pieces.dossier import par_cote
from controle_pieces.extract import extraire
from controle_pieces.locate import localiser, mots_significatifs

ERREURS = json.loads(ERREURS_PLANTEES.read_text(encoding="utf-8"))["erreurs"]


@pytest.fixture(scope="module")
def pieces():
    return par_cote()


def _prononces(chemin, pieces):
    """Les affirmations sur lesquelles la localisation prend position."""
    resultats = []
    for a in extraire(chemin.read_text(encoding="utf-8")):
        if a.porte_une_valeur and controler(a.valeur, pieces[a.cote_citee].texte).verdict == "confirme":
            continue
        loc = localiser(a)
        if loc.classement in ("mauvaise_cote", "non_etaye"):
            resultats.append((a, loc))
    return resultats


def _erreur_correspondante(affirmation):
    """La valeur prime sur la citation : « pièce n° 7 » apparait dans plusieurs
    textes de remplacement et ne discrimine rien."""
    if affirmation.valeur_brute:
        for e in ERREURS:
            if affirmation.valeur_brute in e["apres"]:
                return e
    for e in ERREURS:
        if affirmation.citation in e["apres"] and affirmation.citation not in e["avant"]:
            return e
    return None


# --- Les mots significatifs -----------------------------------------------


def test_les_mots_vides_sont_ecartes():
    mots = mots_significatifs("La société a conclu le contrat de prestation")
    assert "societe" not in mots and "contrat" not in mots
    assert "conclu" in mots and "prestation" in mots


def test_les_accents_ne_changent_rien():
    assert mots_significatifs("réserve") == mots_significatifs("reserve")


# --- Ce sur quoi la localisation refuse de se prononcer --------------------


def test_un_entier_nu_est_indecidable():
    """« huit semaines » et « huit jours ouvrés » portent le meme 8."""
    affirmation = next(
        a for a in extraire(ACTE_PIEGE.read_text(encoding="utf-8"))
        if a.type == "nombre"
    )
    loc = localiser(affirmation)
    assert loc.classement == "indecidable"
    assert loc.methode == "entier_non_discriminant"


def test_le_recouvrement_de_mots_ne_prononce_jamais():
    """Il propose une piste, il ne tranche pas."""
    for a in extraire(ACTE_PIEGE.read_text(encoding="utf-8")):
        loc = localiser(a)
        if loc.methode == "recouvrement_de_mots":
            assert loc.classement == "indecidable"


# --- La garantie : aucune fausse alerte sur l'acte sain --------------------


def test_aucun_classement_sur_l_acte_sain(pieces):
    """L'acte genere est exact : la localisation ne doit rien y trouver."""
    faux_positifs = _prononces(ACTE_LLM, pieces)
    assert faux_positifs == [], [
        (a.claim_id, a.valeur_brute, loc.classement) for a, loc in faux_positifs
    ]


# --- Le rappel sur l'acte piege -------------------------------------------


def test_sept_erreurs_plantees_sont_classees(pieces):
    assert len(_prononces(ACTE_PIEGE, pieces)) == 7


def test_chaque_classement_est_conforme_a_l_erreur_plantee(pieces):
    """Le coeur du test : le classement obtenu doit etre celui declare."""
    for a, loc in _prononces(ACTE_PIEGE, pieces):
        erreur = _erreur_correspondante(a)
        assert erreur is not None, f"{loc.claim_id} : aucune erreur plantee correspondante"
        assert loc.classement == erreur["classement_attendu"], (
            f"{loc.claim_id} ({a.valeur_brute}) : {loc.classement} "
            f"au lieu de {erreur['classement_attendu']} attendu pour {erreur['erreur_id']}"
        )


def test_les_mauvaises_cotes_designent_la_bonne_piece(pieces):
    """Il ne suffit pas de dire « mauvaise cote » : il faut dire laquelle."""
    attendu = {
        "30 juin 2024": 4,        # E-07 : la date est celle de la facture
        "44 400 € HT": 4,         # E-03 : le montant est celui de la facture du lot 1
        "29 novembre 2024": 3,    # E-04 : la date vient de l'avenant jamais signe
    }
    trouve = {
        a.valeur_brute: loc.cote_probable
        for a, loc in _prononces(ACTE_PIEGE, pieces)
        if loc.classement == "mauvaise_cote"
    }
    assert trouve == attendu


def test_la_piece_decisive_est_bien_identifiee(pieces):
    """E-04 renverse le litige : la date vient du projet d'avenant non signe."""
    loc = next(
        loc for a, loc in _prononces(ACTE_PIEGE, pieces)
        if a.valeur_brute == "29 novembre 2024"
    )
    assert loc.classement == "mauvaise_cote"
    assert loc.cote_probable == 3
    assert loc.methode == "valeur_normalisee"


def test_les_erreurs_semantiques_restent_pour_le_juge(pieces):
    """Cinq erreurs ne sont pas decidables sur les valeurs, et c'est normal."""
    couvertes = {
        _erreur_correspondante(a)["erreur_id"]
        for a, _ in _prononces(ACTE_PIEGE, pieces)
        if _erreur_correspondante(a)
    }
    restantes = {e["erreur_id"] for e in ERREURS} - couvertes
    assert restantes == {"E-05", "E-06", "E-08", "E-10", "E-12"}
