"""Normalisation et comparaison deterministes des valeurs.

Montants, dates et pourcentages sont compares exactement : sur ces types une
regle bat un juge, et elle est gratuite et reproductible. Le modele est garde
pour la semantique.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

MOIS = {
    m: i
    for i, m in enumerate(
        "janvier février mars avril mai juin juillet août "
        "septembre octobre novembre décembre".split(),
        start=1,
    )
}

# « un » et « une » sont absents : ce sont des articles bien plus souvent
# que des nombres.
NOMBRES_EN_LETTRES = {
    "deux": 2, "trois": 3, "quatre": 4, "cinq": 5,
    "six": 6, "sept": 7, "huit": 8, "neuf": 9, "dix": 10, "onze": 11,
    "douze": 12, "treize": 13, "quatorze": 14, "quinze": 15, "seize": 16,
    "dix-sept": 17, "dix-huit": 18, "dix-neuf": 19, "vingt": 20,
    "trente": 30, "quarante": 40, "cinquante": 50, "soixante": 60,
}

# Toutes les variantes d'espace qui separent les milliers en francais.
ESPACES = "     "


def normaliser_texte(texte: str) -> str:
    """Forme de travail : sans gras markdown, espaces uniformisees."""
    texte = unicodedata.normalize("NFC", texte).replace("*", "")
    for e in ESPACES[1:]:
        texte = texte.replace(e, " ")
    return texte


# --- Montants ---------------------------------------------------------------

# 62 400,00 € / 62.400 euros / 148 000 € HT / 25 000,00 euros
MONTANT = re.compile(
    r"(?P<nombre>\d{1,3}(?:[" + ESPACES + r"\.]\d{3})*(?:,\d{1,2})?|\d+(?:,\d{1,2})?)"
    r"\s*(?:€|euros?|EUR)"
    r"(?P<qualificatif>\s*(?:HT|TTC|hors taxes|toutes taxes comprises))?",
    re.IGNORECASE,
)


def normaliser_montant(brut: str) -> Decimal | None:
    """« 62 400,00 € » et « 62.400 euros » donnent le meme Decimal."""
    nettoye = normaliser_texte(brut)
    nettoye = re.sub(r"(?:€|euros?|EUR|HT|TTC)", "", nettoye, flags=re.IGNORECASE)
    nettoye = nettoye.strip()
    # Le point est un separateur de milliers en francais, pas un decimal.
    for e in ESPACES:
        nettoye = nettoye.replace(e, "")
    nettoye = nettoye.replace(".", "").replace(",", ".")
    try:
        return Decimal(nettoye)
    except (InvalidOperation, ValueError):
        return None


def _qualifier(texte: str, debut: int, fin: int, capture: str | None) -> str | None:
    """HT ou TTC, pris apres le montant, ou a defaut dans ce qui precede.

    Dans une facture, la mention est souvent dans le libelle de la ligne
    (« Total HT | 59 200,00 € ») et non accolee au chiffre.
    """
    if capture:
        c = capture.strip().lower()
        return "TTC" if "ttc" in c or "toutes taxes" in c else "HT"

    # Une ligne de tableau est une ligne de facture : deborder ferait deteindre
    # le « Total HT » d'une ligne sur la TVA de la suivante.
    debut_ligne = texte.rfind("\n", 0, debut) + 1
    amont = normaliser_texte(texte[debut_ligne:debut]).lower()
    # On prend la mention la plus proche du montant, donc la derniere trouvee.
    dernier_ht = max(amont.rfind(" ht"), amont.rfind("hors taxes"))
    dernier_ttc = max(amont.rfind("ttc"), amont.rfind("toutes taxes"))
    if dernier_ht == dernier_ttc == -1:
        return None
    return "TTC" if dernier_ttc > dernier_ht else "HT"


# --- Dates ------------------------------------------------------------------

DATE_LETTRES = re.compile(
    r"\b(\d{1,2})(?:er)?\s+(" + "|".join(MOIS) + r")\s+((?:19|20)\d{2})\b",
    re.IGNORECASE,
)
DATE_CHIFFRES = re.compile(r"\b(\d{1,2})/(\d{1,2})/((?:19|20)\d{2})\b")
DATE_ISO = re.compile(r"\b((?:19|20)\d{2})-(\d{2})-(\d{2})\b")


def normaliser_date(brut: str) -> date | None:
    """« 12 janvier 2022 », « 12/01/2022 » et « 2022-01-12 » donnent la meme date."""
    texte = normaliser_texte(brut)
    if m := DATE_LETTRES.search(texte):
        jour, mois, annee = m.groups()
        return _construire(int(annee), MOIS[mois.lower()], int(jour))
    if m := DATE_CHIFFRES.search(texte):
        jour, mois, annee = m.groups()
        return _construire(int(annee), int(mois), int(jour))
    if m := DATE_ISO.search(texte):
        annee, mois, jour = m.groups()
        return _construire(int(annee), int(mois), int(jour))
    return None


def _construire(annee: int, mois: int, jour: int) -> date | None:
    try:
        return date(annee, mois, jour)
    except ValueError:
        return None


# --- Pourcentages et nombres ecrits en lettres ------------------------------

POURCENTAGE = re.compile(r"(\d+(?:,\d+)?)\s*%")
NOMBRE_LETTRES = re.compile(
    r"\b(" + "|".join(sorted(NOMBRES_EN_LETTRES, key=len, reverse=True)) + r")\b"
    r"(?:\s*\((\d+)\))?",
    re.IGNORECASE,
)


# --- Valeurs reperees dans un texte -----------------------------------------


@dataclass(frozen=True)
class Valeur:
    """Une valeur factuelle, sous sa forme brute et sous sa forme comparable."""

    type: str  # montant | date | pourcentage | nombre
    brut: str
    normalisee: str
    qualificatif: str | None = None

    @property
    def cle(self) -> tuple[str, str, str | None]:
        """Ce sur quoi porte la comparaison."""
        return (self.type, self.normalisee, self.qualificatif)


def extraire_valeurs(texte: str) -> list[Valeur]:
    """Toutes les valeurs normalisables d'un texte, sans doublon."""
    texte = normaliser_texte(texte)
    trouvees: dict[tuple, Valeur] = {}

    for m in MONTANT.finditer(texte):
        valeur = normaliser_montant(m.group("nombre"))
        if valeur is None:
            continue
        v = Valeur(
            type="montant",
            brut=m.group(0).strip(),
            normalisee=f"{valeur:.2f}",
            qualificatif=_qualifier(texte, m.start(), m.end(), m.group("qualificatif")),
        )
        trouvees.setdefault(v.cle, v)

    for motif in (DATE_LETTRES, DATE_CHIFFRES, DATE_ISO):
        for m in motif.finditer(texte):
            d = normaliser_date(m.group(0))
            if d is None:
                continue
            v = Valeur(type="date", brut=m.group(0), normalisee=d.isoformat())
            trouvees.setdefault(v.cle, v)

    for m in POURCENTAGE.finditer(texte):
        brut = m.group(1).replace(",", ".")
        v = Valeur(type="pourcentage", brut=m.group(0), normalisee=f"{Decimal(brut):g}")
        trouvees.setdefault(v.cle, v)

    for m in NOMBRE_LETTRES.finditer(texte):
        n = NOMBRES_EN_LETTRES[m.group(1).lower()]
        v = Valeur(type="nombre", brut=m.group(0), normalisee=str(n))
        trouvees.setdefault(v.cle, v)

    return list(trouvees.values())


# --- Comparaison a la piece citee -------------------------------------------


@dataclass(frozen=True)
class Controle:
    """Verdict deterministe d'une valeur face au texte d'une piece."""

    valeur: Valeur
    verdict: str  # confirme | contredit | indecidable
    motif: str


def controler(valeur: Valeur, texte_piece: str) -> Controle:
    """Confronte une valeur au texte de la piece citee.

    - `confirme`   : la valeur y figure, avec le meme qualificatif.
    - `contredit`  : la valeur y figure mais pas avec ce qualificatif, ou bien
                     elle en est absente alors que la piece parle bien de ce
                     type de valeur.
    - `indecidable`: la piece ne contient aucune valeur de ce type ; c'est au
                     juge de trancher.
    """
    if valeur.type == "nombre":
        # « quinze reserves » et « quinze jours ouvres » portent le meme entier :
        # un entier nu n'est decidable qu'avec son contexte.
        return Controle(
            valeur,
            "indecidable",
            "entier isole : non decidable sans son contexte, renvoye au juge",
        )

    presentes = extraire_valeurs(texte_piece)
    memes_types = [v for v in presentes if v.type == valeur.type]

    if any(v.cle == valeur.cle for v in memes_types):
        return Controle(valeur, "confirme", "valeur presente a l'identique")

    if valeur.type == "montant":
        memes_nombres = [v for v in memes_types if v.normalisee == valeur.normalisee]
        if memes_nombres:
            # Une contradiction suppose DEUX mentions explicites et differentes.
            # Une mention absente d'un cote est une imprecision, pas une erreur.
            qualifies = {v.qualificatif for v in memes_nombres if v.qualificatif}
            if valeur.qualificatif and qualifies and valeur.qualificatif not in qualifies:
                return Controle(
                    valeur,
                    "contredit",
                    f"montant present mais qualifie {', '.join(sorted(qualifies))} "
                    f"et non {valeur.qualificatif}",
                )
            return Controle(
                valeur,
                "confirme",
                "valeur presente ; la qualification HT/TTC n'est explicite que "
                "d'un seul cote",
            )

    if not memes_types:
        return Controle(
            valeur, "indecidable", f"la piece ne contient aucune valeur de type {valeur.type}"
        )

    return Controle(valeur, "contredit", "valeur absente de la piece citee")
