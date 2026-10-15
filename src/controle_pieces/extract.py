"""Decoupage de l'acte en affirmations citees.

Une citation soutient ce qui la precede. Une affirmation porte au plus une
valeur : un montant et une date peuvent etre vrais separement.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .checks import Valeur, extraire_valeurs

# « (pièce n° 6) », « (pièce n° 1, article 4) », « (pièce n° 7, message 2) ».
CITATION = re.compile(r"\((pièces?\s*n\s*°\s*(\d+)[^)]*)\)", re.IGNORECASE)

# Les en-tetes et le dispositif ne portent pas d'affirmation de fait citee.
LIGNES_IGNOREES = re.compile(r"^\s*(#{1,6}\s|---\s*$)")


@dataclass(frozen=True)
class Affirmation:
    """Une assertion de l'acte, rattachee a la cote qu'elle invoque."""

    claim_id: str
    texte: str
    cote_citee: int
    citation: str
    type: str  # montant | date | pourcentage | nombre | enonce
    valeur_brute: str | None = None
    valeur_normalisee: str | None = None
    qualificatif: str | None = None
    valeur: Valeur | None = field(default=None, repr=False, compare=False)
    # Position du segment dans l'acte. Sert au rattachement exact d'une alerte
    # a une erreur plantee : un chevauchement de positions ne se discute pas.
    debut: int = -1
    fin: int = -1

    @property
    def porte_une_valeur(self) -> bool:
        return self.type != "enonce"


def _paragraphes(acte: str) -> list[str]:
    blocs = []
    for bloc in acte.split("\n\n"):
        lignes = [l for l in bloc.splitlines() if not LIGNES_IGNOREES.match(l)]
        texte = " ".join(l.strip() for l in lignes).strip()
        if texte:
            blocs.append(texte)
    return blocs


def _positions(acte: str) -> list[tuple[int, int]]:
    """Position (debut, fin) du segment soutenu par chaque citation de l'acte.

    Le segment part de la citation precedente, sans franchir le paragraphe.
    """
    debuts_paragraphes = [0] + [m.end() for m in re.finditer(r"\n\n", acte)]
    positions, precedente = [], 0
    for m in CITATION.finditer(acte):
        paragraphe = max(d for d in debuts_paragraphes if d <= m.start())
        positions.append((max(precedente, paragraphe), m.end()))
        precedente = m.end()
    return positions


def _segments_cites(acte: str) -> list[tuple[str, int, str, int, int]]:
    """(texte, cote citee, citation, debut, fin) pour chaque citation."""
    segments = []
    for paragraphe in _paragraphes(acte):
        precedent = 0
        for m in CITATION.finditer(paragraphe):
            texte = paragraphe[precedent : m.start()].strip(" ;,.")
            precedent = m.end()
            if texte:
                segments.append((texte, int(m.group(2)), m.group(1).strip(), -1, -1))

    # Les citations du texte brut sont dans le meme ordre : on y raccroche les
    # positions sans toucher au texte, pour ne pas invalider le cache du juge.
    brutes = _positions(acte)
    if len(brutes) == len(segments):
        segments = [
            (t, c, ci, *brutes[i]) for i, (t, c, ci, _, _) in enumerate(segments)
        ]
    return segments


def extraire(acte: str) -> list[Affirmation]:
    """Toutes les affirmations citees de l'acte, numerotees dans l'ordre."""
    affirmations: list[Affirmation] = []
    compteur = 0

    for texte, cote, citation, debut, fin in _segments_cites(acte):
        valeurs = extraire_valeurs(texte)
        if not valeurs:
            compteur += 1
            affirmations.append(
                Affirmation(
                    claim_id=f"C-{compteur:03d}",
                    texte=texte,
                    cote_citee=cote,
                    citation=citation,
                    type="enonce",
                    debut=debut,
                    fin=fin,
                )
            )
            continue

        for v in valeurs:
            compteur += 1
            affirmations.append(
                Affirmation(
                    claim_id=f"C-{compteur:03d}",
                    texte=texte,
                    cote_citee=cote,
                    citation=citation,
                    type=v.type,
                    valeur_brute=v.brut,
                    valeur_normalisee=v.normalisee,
                    qualificatif=v.qualificatif,
                    valeur=v,
                    debut=debut,
                    fin=fin,
                )
            )

    return affirmations


def resume(affirmations: list[Affirmation]) -> dict:
    """Comptages utiles pour le rapport."""
    from collections import Counter

    return {
        "affirmations": len(affirmations),
        "par_type": dict(Counter(a.type for a in affirmations)),
        "par_cote": dict(sorted(Counter(a.cote_citee for a in affirmations).items())),
        "avec_valeur": sum(1 for a in affirmations if a.porte_une_valeur),
    }
