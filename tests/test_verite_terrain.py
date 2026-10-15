"""La verite terrain est l'etalon du harnais : si elle ment, tout ment.

Le rattachement d'un fait a une seule piece est l'hypothese qui rend la notion
de mauvaise cote definissable.
"""

from __future__ import annotations

import json
import re
import unicodedata
from datetime import date
from decimal import Decimal

import pytest

from conftest import MOIS, PIECES, RACINE, normaliser_espaces

BORDEREAU = json.loads((RACINE / "dossier" / "bordereau.json").read_text("utf-8"))
VERITE = json.loads((RACINE / "dossier" / "verite_terrain.json").read_text("utf-8"))

PAR_DOC_ID = {p["doc_id"]: p for p in BORDEREAU["pieces"]}
TYPES_ADMIS = set(VERITE["types"])


def texte_comparable(texte: str) -> str:
    """Forme sur laquelle on compare : sans gras markdown, espaces normalisees."""
    texte = unicodedata.normalize("NFC", texte).replace("*", "")
    return re.sub(r"\s+", " ", normaliser_espaces(texte)).strip()


@pytest.fixture(scope="module")
def corpus() -> dict[str, str]:
    """Texte comparable de chaque piece, indexe par doc_id."""
    return {
        doc_id: texte_comparable((PIECES / p["fichier"]).read_text("utf-8"))
        for doc_id, p in PAR_DOC_ID.items()
    }


# --- Le bordereau -------------------------------------------------------------


def test_le_bordereau_couvre_toutes_les_pieces_du_dossier():
    fichiers_declares = {p["fichier"] for p in BORDEREAU["pieces"]}
    fichiers_presents = {f.name for f in PIECES.glob("P*.md")}
    assert fichiers_declares == fichiers_presents


def test_les_cotes_sont_contigues_de_1_a_10():
    cotes = sorted(p["cote"] for p in BORDEREAU["pieces"])
    assert cotes == list(range(1, 11))


def test_les_doc_id_sont_uniques():
    doc_ids = [p["doc_id"] for p in BORDEREAU["pieces"]]
    assert len(doc_ids) == len(set(doc_ids))


def test_la_date_de_piece_du_bordereau_figure_dans_la_piece(corpus):
    """Le bordereau ne doit pas dater une piece autrement qu'elle-meme."""
    for doc_id, piece in PAR_DOC_ID.items():
        annee, mois, jour = (int(x) for x in piece["date_piece"].split("-"))
        libelle_mois = [m for m, i in MOIS.items() if i == mois][0]
        attendu = f"{jour} {libelle_mois} {annee}"
        assert attendu in corpus[doc_id], (
            f"{doc_id} : le bordereau annonce le {attendu}, absent de la piece"
        )


# --- Structure de la verite terrain -------------------------------------------


def test_les_fact_id_sont_uniques_et_numerotes_sans_trou():
    ids = [f["fact_id"] for f in VERITE["faits"]]
    assert len(ids) == len(set(ids))
    attendus = [f"F-{i:03d}" for i in range(1, len(ids) + 1)]
    assert ids == attendus


def test_chaque_fait_a_les_champs_requis():
    requis = {"fact_id", "doc_id", "type", "valeur", "libelle", "extrait"}
    for fait in VERITE["faits"]:
        manquants = requis - fait.keys()
        assert not manquants, f"{fait.get('fact_id')} : champs manquants {manquants}"


def test_chaque_fait_pointe_vers_une_piece_du_bordereau():
    for fait in VERITE["faits"]:
        assert fait["doc_id"] in PAR_DOC_ID, (
            f"{fait['fact_id']} : doc_id inconnu {fait['doc_id']}"
        )


def test_chaque_fait_a_un_type_admis():
    for fait in VERITE["faits"]:
        assert fait["type"] in TYPES_ADMIS, (
            f"{fait['fact_id']} : type inconnu {fait['type']}"
        )


def test_toutes_les_pieces_portent_au_moins_deux_faits():
    """Une piece sans fait ne servirait a rien dans le dossier."""
    from collections import Counter

    compte = Counter(f["doc_id"] for f in VERITE["faits"])
    for doc_id in PAR_DOC_ID:
        assert compte[doc_id] >= 2, f"{doc_id} : {compte[doc_id]} fait(s) seulement"


def test_les_quatre_types_sont_representes():
    types = {f["type"] for f in VERITE["faits"]}
    assert types == TYPES_ADMIS, f"types absents : {TYPES_ADMIS - types}"


# --- Le coeur : l'extrait doit exister, et une seule fois -------------------


def test_chaque_extrait_figure_mot_pour_mot_dans_sa_piece(corpus):
    for fait in VERITE["faits"]:
        extrait = texte_comparable(fait["extrait"])
        assert extrait in corpus[fait["doc_id"]], (
            f"{fait['fact_id']} : extrait introuvable dans {fait['doc_id']}\n"
            f"  cherche : {extrait!r}"
        )


def test_aucun_extrait_n_apparait_dans_une_autre_piece(corpus):
    """Sans cette unicite, « mauvaise cote » n'aurait pas de sens : un fait
    presentable dans deux pieces rendrait le verdict du juge indecidable."""
    for fait in VERITE["faits"]:
        extrait = texte_comparable(fait["extrait"])
        intrus = [
            doc_id
            for doc_id, texte in corpus.items()
            if doc_id != fait["doc_id"] and extrait in texte
        ]
        assert not intrus, (
            f"{fait['fact_id']} : extrait egalement present dans {intrus}\n"
            f"  extrait : {extrait!r}"
        )


# --- La valeur normalisee doit correspondre a l'extrait -----------------------

MONTANT = re.compile(r"(\d[\d ]*(?:,\d{2})?)\s*(?:€|euros)")
DATE_FR = re.compile(
    r"\b(\d{1,2}) (janvier|février|mars|avril|mai|juin|juillet|août|"
    r"septembre|octobre|novembre|décembre) (20\d{2})\b"
)


def test_les_montants_annonces_se_lisent_dans_leur_extrait():
    for fait in VERITE["faits"]:
        if fait["type"] != "montant":
            continue
        extrait = texte_comparable(fait["extrait"])
        trouves = {
            Decimal(m.replace(" ", "").replace(",", "."))
            for m in MONTANT.findall(extrait)
        }
        assert Decimal(fait["valeur"]) in trouves, (
            f"{fait['fact_id']} : valeur {fait['valeur']} absente de l'extrait "
            f"(montants lus : {sorted(trouves)})"
        )


def test_les_dates_annoncees_se_lisent_dans_leur_extrait():
    for fait in VERITE["faits"]:
        if fait["type"] != "date":
            continue
        extrait = texte_comparable(fait["extrait"])
        trouvees = {
            date(int(a), MOIS[m], int(j)) for j, m, a in DATE_FR.findall(extrait)
        }
        attendue = date.fromisoformat(fait["valeur"])
        assert attendue in trouvees, (
            f"{fait['fact_id']} : date {fait['valeur']} absente de l'extrait "
            f"(dates lues : {sorted(trouvees)})"
        )


# --- Les pieges du dossier doivent etre couverts par la verite terrain ---------


def test_la_verite_terrain_couvre_les_trois_pieges_du_dossier():
    """Sans ces trois faits, le dossier piege n'aurait rien a mesurer."""
    valeurs = {f["fact_id"]: f for f in VERITE["faits"]}

    # 1. La clause penale vit dans le contrat, pas dans le courrier qui l'applique.
    penalite = next(f for f in VERITE["faits"] if "0,5 %" in f["extrait"])
    assert penalite["doc_id"] == "D-CTR-001"
    calcul = next(f for f in VERITE["faits"] if f["valeur"] == "2368.00")
    assert calcul["doc_id"] == "D-CTS-008"

    # 2. L'avenant n'a jamais ete signe : c'est le cas « introuvable ».
    avenant = next(f for f in VERITE["faits"] if "Sans retour signé" in f["extrait"])
    assert avenant["doc_id"] == "D-AVE-003"

    # 3. Deux montants proches, dans deux pieces differentes.
    montants = {
        f["valeur"]: f["doc_id"] for f in VERITE["faits"] if f["type"] == "montant"
    }
    assert montants["62400.00"] == "D-BDC-002"
    assert montants["59200.00"] in {"D-CTR-001", "D-FAC-006"}
    assert valeurs  # garde-fou : la verite terrain n'est pas vide
