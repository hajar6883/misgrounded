"""Derive de renumerotation, et preuve que la parade tient.

Pas un test d'exemple : une garantie. Quel que soit le point d'insertion, un
acte qui reference des identifiants stables ne derive jamais.
"""

from __future__ import annotations

import pytest

from controle_pieces import renumber
from controle_pieces.chemins import ACTE_LLM
from controle_pieces.dossier import Piece, charger_bordereau


@pytest.fixture(scope="module")
def acte() -> str:
    return ACTE_LLM.read_text(encoding="utf-8")


# --- L'insertion elle-meme ------------------------------------------------


def test_l_insertion_decale_les_cotes_suivantes():
    avant = charger_bordereau()
    apres = renumber.inserer_piece(avant)

    assert len(apres) == len(avant) + 1
    assert [p.cote for p in apres] == list(range(1, len(avant) + 2))

    # Avant le point d'insertion : rien ne bouge.
    assert apres[0].doc_id == avant[0].doc_id
    assert apres[1].doc_id == avant[1].doc_id
    # A la cote 3 : la nouvelle piece.
    assert apres[2].doc_id == renumber.PIECE_INSEREE.doc_id
    # Apres : tout est decale d'exactement un rang.
    for p in avant:
        if p.cote >= renumber.PIECE_INSEREE.cote:
            nouvelle = next(q for q in apres if q.doc_id == p.doc_id)
            assert nouvelle.cote == p.cote + 1


def test_les_doc_id_survivent_a_l_insertion():
    """C'est toute l'idee : la cote bouge, l'identifiant jamais."""
    avant = charger_bordereau()
    apres = renumber.inserer_piece(avant)
    assert {p.doc_id for p in avant} < {p.doc_id for p in apres}


# --- La derive naive ------------------------------------------------------


def test_l_acte_naif_derive_reellement(acte):
    derive = renumber.derive_naive(acte)
    assert derive.citations == 25
    assert derive.cassees == 14
    assert derive.taux == pytest.approx(0.56)


def test_la_derive_naive_epargne_les_cotes_anterieures(acte):
    """Une citation avant le point d'insertion ne peut pas deriver."""
    derive = renumber.derive_naive(acte)
    for cote, _, _ in derive.details:
        assert cote >= renumber.PIECE_INSEREE.cote


def test_chaque_citation_cassee_designe_bien_un_autre_document(acte):
    derive = renumber.derive_naive(acte)
    for _, attendu, obtenu in derive.details:
        assert attendu != obtenu


# --- La parade ------------------------------------------------------------


def test_l_identifiant_stable_annule_la_derive(acte):
    """LE test du projet : derive = 0, pas « derive faible »."""
    assert renumber.derive_protegee(acte).cassees == 0


def test_la_forme_interne_ne_contient_plus_aucune_cote(acte):
    """Si une cote subsistait en dur, elle deriverait en silence."""
    stable = renumber.vers_identifiants_stables(acte)
    assert not renumber.CITATION.search(stable)
    assert stable.count("{{doc:") == 25


def test_l_aller_retour_est_sans_perte(acte):
    """Convertir puis reexporter sur le meme bordereau redonne l'acte."""
    stable = renumber.vers_identifiants_stables(acte)
    assert renumber.exporter(stable) == acte


def test_la_garantie_tient_pour_tout_point_d_insertion(acte):
    """Pas seulement pour la cote 3 : pour toutes."""
    avant = charger_bordereau()
    for cote in range(1, len(avant) + 2):
        nouvelle = Piece(
            cote=cote,
            doc_id=f"D-TST-{cote:03d}",
            fichier="inexistant.md",
            titre="piece de test",
            nature="test",
            date_piece="2025-01-01",
        )
        apres = renumber.inserer_piece(avant, nouvelle)
        protegee = renumber.derive_protegee(acte, avant, apres)
        assert protegee.cassees == 0, f"derive a l'insertion en cote {cote}"


def test_la_garantie_tient_meme_si_le_bordereau_est_entierement_reordonne(acte):
    """Cas extreme : on inverse tout l'ordre des pieces."""
    avant = charger_bordereau()
    inverse = tuple(
        Piece(
            cote=len(avant) - p.cote + 1,
            doc_id=p.doc_id,
            fichier=p.fichier,
            titre=p.titre,
            nature=p.nature,
            date_piece=p.date_piece,
        )
        for p in avant
    )
    assert renumber.derive_protegee(acte, avant, inverse).cassees == 0
    # Et la version naive, elle, s'effondre.
    assert renumber.derive_naive(acte, avant, inverse).cassees > 0


# --- Robustesse -----------------------------------------------------------


def test_une_cote_inconnue_n_est_pas_convertie():
    """On ne fabrique pas un identifiant pour une cote qui n'existe pas."""
    texte = "Comme le montre la pièce n° 99, le fait est etabli."
    assert renumber.vers_identifiants_stables(texte) == texte


def test_un_jeton_inconnu_reste_intact_a_l_export():
    texte = "Voir la pièce {{doc:D-INEXISTANT}}."
    assert renumber.exporter(texte) == texte


def test_les_variantes_d_ecriture_sont_reconnues():
    """Espace insecable, pluriel, absence d'espace."""
    for variante in ["pièce n° 1", "pièce n°1", "pièces n° 1", "pièce n ° 1"]:
        assert renumber.cotes_citees(f"Voir {variante}.") == [1], variante


def test_le_rapport_de_comparaison_est_complet(acte):
    rapport = renumber.comparer(acte)
    assert rapport["citations_dans_l_acte"] == 25
    assert rapport["naif"]["citations_cassees"] == 14
    assert rapport["identifiant_stable"]["citations_cassees"] == 0
    assert rapport["piece_inseree"]["doc_id"] == "D-CST-011"


def test_la_majuscule_est_reconnue():
    """Un modele peut commencer une phrase par « Pièce n° 1 »."""
    assert renumber.cotes_citees("Pièce n° 1 : le contrat.") == [1]
    assert "{{doc:D-CTR-001}}" in renumber.vers_identifiants_stables("Pièce n° 1")
