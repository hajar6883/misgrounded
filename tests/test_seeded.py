"""Le dossier piege est l'etalon du rappel : il doit etre irreprochable.

Une erreur non appliquee ferait chuter le rappel pour rien ; une difference
non declaree compterait comme fausse alerte.
"""

from __future__ import annotations

import json

import pytest

from controle_pieces import piegeage
from controle_pieces.chemins import ACTE_LLM, ACTE_PIEGE, ERREURS_PLANTEES

CATEGORIES = {
    "montant_faux",
    "date_fausse",
    "mauvaise_cote",
    "confusion_ht_ttc",
    "fait_invente",
}
VERDICTS = {"contredit", "absent"}
CLASSEMENTS = {"mauvaise_cote", "non_etaye"}


@pytest.fixture(scope="module")
def source() -> str:
    return ACTE_LLM.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def piege() -> str:
    return ACTE_PIEGE.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def journal() -> dict:
    return json.loads(ERREURS_PLANTEES.read_text(encoding="utf-8"))


# --- Les ancrages ---------------------------------------------------------


def test_chaque_ancrage_apparait_exactement_une_fois(source):
    """Un ancrage ambigu appliquerait la substitution au mauvais endroit."""
    for erreur in piegeage.ERREURS:
        assert source.count(erreur.avant) == 1, (
            f"{erreur.erreur_id} : {source.count(erreur.avant)} occurrence(s) "
            f"de {erreur.avant!r}"
        )


def test_la_construction_ne_passe_pas_sur_un_acte_modifie(source):
    """Si l'acte est regenere et qu'un ancrage disparait, ca doit echouer."""
    abime = source.replace(piegeage.ERREURS[0].avant, "texte remplace")
    with pytest.raises(piegeage.AncrageIntrouvable):
        piegeage.verifier_ancrages(abime)


# --- L'acte piege ---------------------------------------------------------


def test_l_acte_piege_est_reproductible_a_l_identique(piege):
    """Reconstruire depuis la source doit redonner le fichier commite."""
    reconstruit, _ = piegeage.construire(ecrire=False)
    assert reconstruit == piege


def test_chaque_substitution_est_bien_presente(piege):
    for erreur in piegeage.ERREURS:
        assert erreur.apres in piege, f"{erreur.erreur_id} : substitution absente"


def test_aucun_texte_d_origine_ne_subsiste(piege):
    for erreur in piegeage.ERREURS:
        # E-11 ajoute une phrase : son texte d'origine est, par construction,
        # un prefixe du texte de remplacement et subsiste donc legitimement.
        if erreur.avant in erreur.apres:
            continue
        assert erreur.avant not in piege, (
            f"{erreur.erreur_id} : le texte d'origine est toujours la"
        )


def test_l_acte_piege_ne_differe_que_par_les_erreurs_declarees(source, piege):
    """Aucune difference clandestine entre les deux actes."""
    attendu = source
    for erreur in piegeage.ERREURS:
        attendu = attendu.replace(erreur.avant, erreur.apres, 1)
    assert piege == attendu


# --- Le journal des erreurs ----------------------------------------------


def test_le_journal_reflete_le_module(journal):
    assert journal["nombre"] == len(piegeage.ERREURS)
    assert len(journal["erreurs"]) == len(piegeage.ERREURS)
    ids_journal = [e["erreur_id"] for e in journal["erreurs"]]
    ids_module = [e.erreur_id for e in piegeage.ERREURS]
    assert ids_journal == ids_module


def test_les_identifiants_sont_uniques_et_numerotes_sans_trou():
    ids = [e.erreur_id for e in piegeage.ERREURS]
    assert ids == [f"E-{i:02d}" for i in range(1, len(ids) + 1)]


def test_les_champs_prennent_des_valeurs_admises():
    for erreur in piegeage.ERREURS:
        assert erreur.categorie in CATEGORIES, erreur.erreur_id
        assert erreur.verdict_attendu in VERDICTS, erreur.erreur_id
        assert erreur.classement_attendu in CLASSEMENTS, erreur.erreur_id
        assert 1 <= erreur.cote_citee <= 10, erreur.erreur_id
        assert erreur.explication.strip(), erreur.erreur_id


def test_la_substitution_change_vraiment_quelque_chose():
    for erreur in piegeage.ERREURS:
        assert erreur.avant != erreur.apres, erreur.erreur_id


# --- La couverture des modes d'echec --------------------------------------


def test_les_cinq_categories_sont_representees():
    """Un rappel agrege sur une seule categorie ne dirait pas grand-chose."""
    presentes = {e.categorie for e in piegeage.ERREURS}
    assert presentes == CATEGORIES, f"categories absentes : {CATEGORIES - presentes}"


def test_les_deux_classements_sont_representes():
    presentes = {e.classement_attendu for e in piegeage.ERREURS}
    assert presentes == CLASSEMENTS


def test_les_erreurs_visent_des_pieces_variees():
    """Concentrer les pieges sur une seule piece biaiserait la mesure."""
    cotes = {e.cote_citee for e in piegeage.ERREURS}
    assert len(cotes) >= 6, f"seulement {len(cotes)} pieces piegees : {sorted(cotes)}"


def test_le_piege_decisif_est_present():
    """L'erreur qui renverse l'issue du litige doit rester dans le lot."""
    e04 = next(e for e in piegeage.ERREURS if e.erreur_id == "E-04")
    assert "29 novembre 2024" in e04.apres
    assert e04.classement_attendu == "mauvaise_cote"

    e01 = next(e for e in piegeage.ERREURS if e.erreur_id == "E-01")
    assert "4 440" in e01.apres
    assert e01.classement_attendu == "non_etaye"


# --- Le rattachement d'une alerte a son erreur ----------------------------


def test_chaque_erreur_a_une_position_exacte(piege):
    """La substitution doit se lire telle quelle a la position enregistree."""
    positions = piegeage.spans()
    assert len(positions) == len(piegeage.ERREURS)
    for erreur in piegeage.ERREURS:
        debut, fin = positions[erreur.erreur_id]
        assert piege[debut:fin] == erreur.apres, erreur.erreur_id


def test_le_segment_qui_couvre_une_erreur_la_rattache():
    debut, fin = piegeage.spans()["E-04"]
    assert piegeage.erreur_du_segment(debut, fin).erreur_id == "E-04"
    # Un segment qui n'effleure que le debut suffit : le chevauchement compte.
    assert piegeage.erreur_du_segment(debut - 50, debut + 5).erreur_id == "E-04"


def test_un_segment_hors_de_toute_erreur_ne_rattache_rien():
    """Sans quoi une fausse alerte serait comptee comme une detection."""
    positions = sorted(piegeage.spans().values())
    # Un intervalle vide, entre deux substitutions consecutives.
    for (_, fin_a), (debut_b, _) in zip(positions, positions[1:]):
        if debut_b - fin_a > 10:
            assert piegeage.erreur_du_segment(fin_a + 1, debut_b - 1) is None
            return
    pytest.fail("aucun intervalle libre trouve")


def test_les_positions_ne_se_chevauchent_pas():
    """Deux erreurs au meme endroit rendraient le rattachement ambigu."""
    positions = sorted(piegeage.spans().values())
    for (_, fin_a), (debut_b, _) in zip(positions, positions[1:]):
        assert fin_a <= debut_b
