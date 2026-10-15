"""Normalisation, extraction et controles deterministes.

Deux garanties : aucune alerte sur l'acte sain, et chaque alerte de l'acte
piege rattachee a une erreur reellement plantee.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from controle_pieces import piegeage
from controle_pieces.checks import (
    Valeur,
    controler,
    extraire_valeurs,
    normaliser_date,
    normaliser_montant,
)
from controle_pieces.chemins import ACTE_LLM, ACTE_PIEGE
from controle_pieces.dossier import par_cote
from controle_pieces.extract import extraire


@pytest.fixture(scope="module")
def pieces():
    return par_cote()


# --- Normalisation des montants -------------------------------------------


@pytest.mark.parametrize(
    "brut, attendu",
    [
        ("48.570 euros", "48570"),          # le point separe les milliers
        ("48 570 €", "48570"),
        ("48 570,00 € TTC", "48570.00"),
        ("148 000 € HT", "148000"),
        ("25 000,00 euros", "25000.00"),
        ("40 euros", "40"),
        ("1 234 567,89 €", "1234567.89"),
    ],
)
def test_les_ecritures_de_montant_convergent(brut, attendu):
    assert normaliser_montant(brut) == Decimal(attendu)


def test_un_montant_illisible_ne_leve_pas_d_exception():
    assert normaliser_montant("beaucoup d'euros") is None


def test_les_montants_egaux_ecrits_autrement_sont_egaux():
    formes = ["59 200 €", "59.200 euros", "59 200,00 €", "59200 EUR"]
    valeurs = {normaliser_montant(f) for f in formes}
    assert len(valeurs) == 1


# --- Normalisation des dates ----------------------------------------------


@pytest.mark.parametrize(
    "brut, attendu",
    [
        ("12 janvier 2022", date(2022, 1, 12)),
        ("12/01/2022", date(2022, 1, 12)),
        ("2022-01-12", date(2022, 1, 12)),
        ("1er avril 2024", date(2024, 4, 1)),
        ("18 octobre 2024", date(2024, 10, 18)),
        ("8 novembre 2024", date(2024, 11, 8)),
    ],
)
def test_les_ecritures_de_date_convergent(brut, attendu):
    assert normaliser_date(brut) == attendu


def test_une_date_impossible_est_rejetee():
    """31 fevrier a la bonne forme et n'existe pas."""
    assert normaliser_date("31 février 2024") is None
    assert normaliser_date("32/01/2024") is None


def test_un_texte_sans_date_ne_donne_rien():
    assert normaliser_date("le contrat a ete signe") is None


# --- Le qualificatif HT / TTC ---------------------------------------------


def test_le_qualificatif_accole_au_montant_est_lu():
    valeurs = {v.normalisee: v for v in extraire_valeurs("un total de 59 200 € HT")}
    assert valeurs["59200.00"].qualificatif == "HT"


def test_le_qualificatif_vient_du_libelle_de_la_ligne(pieces):
    """Sur une facture, la mention est dans le libelle, pas collee au chiffre."""
    montants = {
        v.normalisee: v
        for v in extraire_valeurs(pieces[6].texte)
        if v.type == "montant"
    }
    assert montants["59200.00"].qualificatif == "HT"
    assert montants["71040.00"].qualificatif == "TTC"


def test_le_qualificatif_ne_deborde_pas_d_une_ligne_sur_l_autre(pieces):
    """La ligne de TVA suit un « Total HT » et ne doit pas en heriter."""
    montants = {
        v.normalisee: v
        for v in extraire_valeurs(pieces[6].texte)
        if v.type == "montant"
    }
    assert montants["11840.00"].qualificatif is None


# --- Controle face a la piece citee ---------------------------------------


def test_un_montant_juste_est_confirme(pieces):
    v = Valeur("montant", "59 200 € HT", "59200.00", "HT")
    assert controler(v, pieces[6].texte).verdict == "confirme"


def test_le_meme_montant_mal_qualifie_est_contredit(pieces):
    """Le piege HT/TTC : bonne valeur, mauvaise nature."""
    v = Valeur("montant", "59 200 € TTC", "59200.00", "TTC")
    c = controler(v, pieces[6].texte)
    assert c.verdict == "contredit"
    assert "HT" in c.motif and "TTC" in c.motif


def test_un_montant_absent_est_contredit(pieces):
    v = Valeur("montant", "4 440 €", "4440.00", None)
    assert controler(v, pieces[8].texte).verdict == "contredit"


def test_un_entier_nu_est_renvoye_au_juge(pieces):
    """« quinze reserves » et « quinze jours ouvres » portent le meme entier."""
    v = Valeur("nombre", "quinze", "15")
    c = controler(v, pieces[5].texte)
    assert c.verdict == "indecidable"
    assert "contexte" in c.motif


def test_un_type_absent_de_la_piece_est_indecidable(pieces):
    """Le Kbis ne porte aucun pourcentage : la regle ne tranche pas."""
    v = Valeur("pourcentage", "10 %", "10")
    assert controler(v, pieces[10].texte).verdict == "indecidable"


# --- Extraction des affirmations ------------------------------------------


def test_les_articles_ne_sont_pas_pris_pour_des_nombres():
    """« un contrat » ne porte pas l'entier 1."""
    valeurs = extraire_valeurs("un contrat et une obligation")
    assert not [v for v in valeurs if v.type == "nombre"]


def test_chaque_affirmation_porte_au_plus_une_valeur():
    for a in extraire(ACTE_PIEGE.read_text(encoding="utf-8")):
        if a.type == "enonce":
            assert a.valeur_normalisee is None
        else:
            assert a.valeur_normalisee is not None


def test_les_identifiants_d_affirmation_sont_uniques_et_ordonnes():
    ids = [a.claim_id for a in extraire(ACTE_PIEGE.read_text(encoding="utf-8"))]
    assert ids == [f"C-{i:03d}" for i in range(1, len(ids) + 1)]


def test_toute_affirmation_cite_une_cote_du_bordereau(pieces):
    for a in extraire(ACTE_LLM.read_text(encoding="utf-8")):
        assert a.cote_citee in pieces


def test_l_acte_piege_cite_la_piece_2_contrairement_a_l_original():
    """Effet direct de l'erreur E-03, qui deplace une citation vers la n° 2."""
    cotes_sain = {a.cote_citee for a in extraire(ACTE_LLM.read_text(encoding="utf-8"))}
    cotes_piege = {a.cote_citee for a in extraire(ACTE_PIEGE.read_text(encoding="utf-8"))}
    assert 2 not in cotes_sain
    assert 2 in cotes_piege


# --- Les deux garanties qui comptent --------------------------------------


def _contredits(acte: str, pieces) -> list:
    resultats = []
    for a in extraire(acte):
        if not a.porte_une_valeur:
            continue
        c = controler(a.valeur, pieces[a.cote_citee].texte)
        if c.verdict == "contredit":
            resultats.append(a)
    return resultats


def test_aucune_fausse_alerte_sur_l_acte_sain(pieces):
    """LA garantie : le controle deterministe ne doit rien inventer."""
    faux_positifs = _contredits(ACTE_LLM.read_text(encoding="utf-8"), pieces)
    assert faux_positifs == [], [
        (a.claim_id, a.cote_citee, a.valeur_brute) for a in faux_positifs
    ]


def test_le_controle_deterministe_attrape_sept_erreurs_plantees(pieces):
    detectes = _contredits(ACTE_PIEGE.read_text(encoding="utf-8"), pieces)
    assert len(detectes) == 7


def test_chaque_alerte_correspond_a_une_erreur_reellement_plantee(pieces):
    """Une detection fortuite gonflerait le rappel sans rien prouver.

    Une erreur peut avoir altere soit la valeur (« 2 368 € » -> « 4 440 € »),
    soit la cote citee (« pièce n° 4 » -> « pièce n° 2 »). Une alerte est donc
    rattachable par l'une ou par l'autre.
    """
    for a in _contredits(ACTE_PIEGE.read_text(encoding="utf-8"), pieces):
        rattachee = any(
            a.valeur_brute in e.apres or a.citation in e.apres
            for e in piegeage.ERREURS
        )
        assert rattachee, (
            f"{a.claim_id} : ni la valeur {a.valeur_brute!r} ni la citation "
            f"{a.citation!r} ne viennent d'une erreur plantee"
        )


def test_les_erreurs_semantiques_echappent_bien_au_deterministe(pieces):
    """Elles ne sont pas oubliees : elles sont renvoyees au juge.

    E-05 date la signature de l'avenant du 17 septembre 2024 -- date qui figure
    bien dans la piece n° 3, mais pour un comite de pilotage. Une regle sur les
    valeurs ne peut pas trancher cela, et c'est la raison d'etre du juge.
    """
    bruts = {a.valeur_brute for a in _contredits(ACTE_PIEGE.read_text(encoding="utf-8"), pieces)}
    assert "17 septembre 2024" not in bruts
    assert "21 décembre 2024" not in bruts


# --- L'asymetrie du qualificatif HT / TTC ---------------------------------


def test_un_montant_non_qualifie_n_est_pas_une_contradiction(pieces):
    """« 148 000 € » pour « 148 000 € HT » est imprecis, pas faux.

    Regle trouvee en verifiant les resumes du bordereau : traiter « sans
    mention » comme un qualificatif a part entiere inondait le controle de
    fausses alertes.
    """
    v = Valeur("montant", "148 000 €", "148000.00", None)
    assert controler(v, pieces[1].texte).verdict == "confirme"


def test_un_qualificatif_absent_de_la_piece_n_est_pas_une_contradiction(pieces):
    """La piece n'ecrit ni HT ni TTC sur ce montant : on ne peut pas trancher."""
    v = Valeur("montant", "2 368 € HT", "2368.00", "HT")
    assert controler(v, pieces[8].texte).verdict == "confirme"


def test_deux_qualificatifs_explicites_et_differents_se_contredisent(pieces):
    """La vraie contradiction, celle que l'erreur E-02 exploite."""
    v = Valeur("montant", "59 200 € TTC", "59200.00", "TTC")
    assert controler(v, pieces[6].texte).verdict == "contredit"
