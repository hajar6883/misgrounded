"""Ou le fait se trouve-t-il reellement ?

Distingue la mauvaise cote (fait vrai, autre piece) de l'hallucination (fait
nulle part). Ne prononce que sur les valeurs normalisees ; entiers nus et
recouvrement de mots sont renvoyes au juge.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from .checks import Valeur, extraire_valeurs
from .dossier import Piece, charger_bordereau
from .extract import Affirmation

# Mots vides du francais juridique : presents partout, donc sans pouvoir
# discriminant. Une liste courte suffit et reste lisible.
MOTS_VIDES = {
    "la", "le", "les", "de", "des", "du", "un", "une", "et", "en", "au", "aux",
    "a", "par", "pour", "dans", "sur", "que", "qui", "ne", "pas", "est", "sont",
    "ete", "etait", "avec", "sans", "ce", "cette", "ces", "son", "sa", "ses",
    "leur", "leurs", "il", "elle", "nous", "vous", "plus", "ou", "si", "se",
    "societe", "contrat", "piece", "article", "lot", "monsieur", "madame",
}


@dataclass(frozen=True)
class Localisation:
    """Ou le fait se trouve reellement, si tant est qu'il se trouve quelque part."""

    claim_id: str
    cote_citee: int
    classement: str  # mauvaise_cote | non_etaye | confirme_a_la_cote
    cotes_candidates: tuple[int, ...]
    methode: str  # valeur_normalisee | recouvrement_de_mots
    score: float

    @property
    def cote_probable(self) -> int | None:
        return self.cotes_candidates[0] if self.cotes_candidates else None


def _sans_accents(texte: str) -> str:
    decompose = unicodedata.normalize("NFD", texte.lower())
    return "".join(c for c in decompose if unicodedata.category(c) != "Mn")


def mots_significatifs(texte: str) -> set[str]:
    """Les mots d'au moins quatre lettres qui ne sont pas des mots vides."""
    mots = re.findall(r"[a-z0-9]+", _sans_accents(texte))
    return {m for m in mots if len(m) >= 4 and m not in MOTS_VIDES}


def _pieces_portant(valeur: Valeur, pieces: tuple[Piece, ...]) -> list[int]:
    """Cotes des pieces ou cette valeur figure, qualificatif compatible."""
    trouvees = []
    for piece in pieces:
        for v in extraire_valeurs(piece.texte):
            if v.type != valeur.type or v.normalisee != valeur.normalisee:
                continue
            # Qualificatif exige a l'identique, contrairement a checks : celui-ci
            # demande « ce montant est-il faux ? », celui-la « ou vit-il ? ».
            if valeur.qualificatif != v.qualificatif:
                continue
            trouvees.append(piece.cote)
            break
    return trouvees


def localiser(affirmation: Affirmation) -> Localisation:
    """Classe une affirmation que la piece citee n'etaye pas."""
    pieces = charger_bordereau()

    # Un entier nu se retrouve partout : le localiser reviendrait a tirer au sort.
    if affirmation.type == "nombre":
        return Localisation(
            claim_id=affirmation.claim_id,
            cote_citee=affirmation.cote_citee,
            classement="indecidable",
            cotes_candidates=(),
            methode="entier_non_discriminant",
            score=0.0,
        )

    if affirmation.porte_une_valeur and affirmation.valeur is not None:
        cotes = _pieces_portant(affirmation.valeur, pieces)
        ailleurs = tuple(c for c in cotes if c != affirmation.cote_citee)
        if affirmation.cote_citee in cotes:
            classement = "confirme_a_la_cote"
        elif ailleurs:
            classement = "mauvaise_cote"
        else:
            classement = "non_etaye"
        return Localisation(
            claim_id=affirmation.claim_id,
            cote_citee=affirmation.cote_citee,
            classement=classement,
            cotes_candidates=ailleurs,
            methode="valeur_normalisee",
            score=1.0 if ailleurs else 0.0,
        )

    # Affirmation sans valeur normalisable : recouvrement de mots.
    mots = mots_significatifs(affirmation.texte)
    if not mots:
        return Localisation(
            claim_id=affirmation.claim_id,
            cote_citee=affirmation.cote_citee,
            classement="non_etaye",
            cotes_candidates=(),
            methode="recouvrement_de_mots",
            score=0.0,
        )

    scores = []
    for piece in pieces:
        commun = mots & mots_significatifs(piece.texte)
        scores.append((len(commun) / len(mots), piece.cote))
    scores.sort(reverse=True)

    meilleur, cote_gagnante = scores[0]
    score_cite = next(s for s, c in scores if c == affirmation.cote_citee)

    # Indice, pas preuve : on propose une piste, on ne prononce jamais.
    candidates = (
        (cote_gagnante,)
        if cote_gagnante != affirmation.cote_citee and meilleur > score_cite
        else ()
    )
    classement = "indecidable"

    return Localisation(
        claim_id=affirmation.claim_id,
        cote_citee=affirmation.cote_citee,
        classement=classement,
        cotes_candidates=candidates,
        methode="recouvrement_de_mots",
        score=round(meilleur, 3),
    )


def localiser_toutes(affirmations: list[Affirmation]) -> list[Localisation]:
    return [localiser(a) for a in affirmations]
