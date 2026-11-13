"""Metriques, et la discipline de methode qui les entoure.

Le test central ne verifie pas un calcul : il verifie que les deux actes ne
sont jamais agreges.
"""

from __future__ import annotations

import pytest

from controle_pieces import piegeage, report


@pytest.fixture(scope="module")
def rapport():
    return report.rapport_complet()


# --- Structure -------------------------------------------------------------


def test_le_rapport_tourne_hors_ligne(rapport):
    """Aucun appel reseau : un relecteur sans cle doit pouvoir tout rejouer."""
    assert set(rapport) == {
        "dossier_piege",
        "acte_genere",
        "mauvaises_cotes",
        "renumerotation",
        "resumes_du_bordereau",
    }


def test_les_deux_actes_sont_rapportes_separement(rapport):
    """La discipline exigee par l'objection MiniCheck."""
    piege, genere = rapport["dossier_piege"], rapport["acte_genere"]
    assert piege["acte"] != genere["acte"]
    # Le rappel n'a de sens que sur le dossier piege.
    assert "rappel_verificateur" in piege
    assert "rappel_verificateur" not in genere
    # Les fausses alertes non plus.
    assert "taux_fausses_alertes" in piege
    assert "taux_fausses_alertes" not in genere


def test_l_acte_genere_ne_parle_pas_de_fausses_alertes(rapport):
    """Sans verite terrain, une alerte est un candidat, pas une fausse alerte."""
    genere = rapport["acte_genere"]
    assert "erreurs_naturelles_candidates" in genere
    assert "candidates" in genere["note"]


# --- Dossier piege ---------------------------------------------------------


def test_les_douze_erreurs_plantees_sont_le_denominateur(rapport):
    assert rapport["dossier_piege"]["erreurs_plantees"] == len(piegeage.ERREURS) == 12


def test_le_rappel_est_un_taux_valide(rapport):
    piege = rapport["dossier_piege"]
    assert 0.0 <= piege["rappel_verificateur"] <= 1.0
    assert piege["erreurs_detectees"] + len(piege["erreurs_manquees"]) == 12


def test_les_regles_seules_attrapent_au_moins_sept_erreurs(rapport):
    """Plancher deterministe : il ne depend d'aucun modele, donc il ne bouge pas.

    Le juge ne peut que faire monter ce chiffre, jamais le faire descendre.
    """
    assert rapport["dossier_piege"]["erreurs_detectees"] >= 7


def test_chaque_alerte_est_tracable(rapport):
    for alerte in rapport["dossier_piege"]["detail"]:
        assert alerte["source"] in ("deterministe", "localisation", "juge")
        assert alerte["claim_id"].startswith("C-")


# --- Renumerotation et resumes --------------------------------------------


def test_la_derive_de_renumerotation_est_bien_de_quatorze_contre_zero(rapport):
    r = rapport["renumerotation"]
    assert r["citations_dans_l_acte"] == 25
    assert r["naif"]["citations_cassees"] == 14
    assert r["identifiant_stable"]["citations_cassees"] == 0


def test_les_resumes_ne_contredisent_pas_leurs_pieces(rapport):
    s = rapport["resumes_du_bordereau"]
    assert s["resumes"] == 10
    assert s["contredites"] == 0
    assert s["taux_confirme"] >= 0.9


# --- Rendu -----------------------------------------------------------------


def test_les_tableaux_se_rendent_sans_le_juge(rapport):
    """Le rapport doit rester lisible tant que la double passe n'a pas tourne."""
    texte = report.tableaux(rapport)
    assert "Dossier piégé" in texte
    assert "Acte réellement généré" in texte
    assert "Dérive de renumérotation" in texte
    assert "Résumés du bordereau" in texte


def test_les_taux_sont_affiches_en_pourcentage(rapport):
    assert "%" in report.tableaux(rapport)
