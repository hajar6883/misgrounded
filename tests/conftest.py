"""Outils de lecture du dossier, partages par les tests.

Ils valident la fixture, pas le pipeline.
"""

from __future__ import annotations

import re
import unicodedata
from decimal import Decimal
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
PIECES = RACINE / "dossier" / "pieces"

# Tous les separateurs d'espace Unicode qu'on peut croiser dans un montant
# francais : espace fine insecable, espace insecable, espace normale.
_ESPACES = dict.fromkeys(map(ord, "     "), None)


def normaliser_espaces(texte: str) -> str:
    """Remplace toute variante d'espace par une espace simple."""
    texte = unicodedata.normalize("NFC", texte)
    return re.sub(r"[    ]", " ", texte)


def en_decimal(montant: str) -> Decimal:
    """« 62 400,00 € » -> Decimal('62400.00'). Tolere les espaces exotiques."""
    nettoye = normaliser_espaces(montant)
    nettoye = nettoye.replace("*", "")  # gras markdown : **44 400,00 €**
    nettoye = nettoye.replace("€", "").replace("euros", "").strip()
    nettoye = nettoye.translate(_ESPACES).replace(",", ".")
    return Decimal(nettoye)


_LIGNE_TABLEAU = re.compile(r"^\s*\|(?P<cellules>.+)\|\s*$")
_MONTANT = re.compile(r"^\*{0,2}[\d   ]+,\d{2}\s*€\*{0,2}$")


def lignes_tableau(texte: str) -> list[list[str]]:
    """Renvoie les lignes de tableau markdown, decoupees en cellules nettoyees."""
    lignes = []
    for brute in texte.splitlines():
        correspondance = _LIGNE_TABLEAU.match(brute)
        if not correspondance:
            continue
        cellules = [c.strip() for c in correspondance.group("cellules").split("|")]
        # On ecarte les separateurs d'en-tete : |---|---|
        if all(set(c) <= set("-: ") for c in cellules):
            continue
        lignes.append(cellules)
    return lignes


def est_montant(cellule: str) -> bool:
    return bool(_MONTANT.match(normaliser_espaces(cellule)))


def totaux(texte: str) -> dict[str, Decimal]:
    """Extrait le triplet HT / TVA / TTC d'une piece, s'il existe."""
    trouves: dict[str, Decimal] = {}
    for cellules in lignes_tableau(texte):
        if len(cellules) < 2 or not est_montant(cellules[-1]):
            continue
        libelle = normaliser_espaces(cellules[0]).replace("*", "").lower()
        valeur = en_decimal(cellules[-1])
        if libelle.startswith("total ht"):
            trouves["ht"] = valeur
        elif libelle.startswith("tva"):
            trouves["tva"] = valeur
        elif libelle.startswith(("total ttc", "net à payer")):
            trouves["ttc"] = valeur
    return trouves


def lignes_de_detail(texte: str) -> list[Decimal]:
    """Montants des lignes de prestation, hors lignes de total et de TVA."""
    montants = []
    for cellules in lignes_tableau(texte):
        if len(cellules) < 2 or not est_montant(cellules[-1]):
            continue
        libelle = normaliser_espaces(cellules[0]).replace("*", "").lower()
        if libelle.startswith(("total", "tva", "net a payer", "net à payer")):
            continue
        montants.append(en_decimal(cellules[-1]))
    return montants


MOIS = {
    m: i
    for i, m in enumerate(
        "janvier février mars avril mai juin juillet août "
        "septembre octobre novembre décembre".split(),
        start=1,
    )
}


def luhn_valide(chiffres: str) -> bool:
    """Clé de Luhn, utilisee par les numeros SIREN (9) et SIRET (14)."""
    nombres = [int(c) for c in chiffres if c.isdigit()]
    total = 0
    for rang, n in enumerate(reversed(nombres)):
        if rang % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


def cle_tva_francaise(siren: str) -> int:
    """Clé du numero de TVA intracommunautaire : (12 + 3 * (SIREN mod 97)) mod 97."""
    return (12 + 3 * (int(siren) % 97)) % 97


@pytest.fixture(scope="session")
def pieces() -> dict[str, str]:
    """Toutes les pieces du dossier, indexees par nom de fichier."""
    fichiers = sorted(PIECES.glob("P*.md"))
    assert fichiers, f"aucune piece trouvee dans {PIECES}"
    return {f.name: f.read_text(encoding="utf-8") for f in fichiers}
