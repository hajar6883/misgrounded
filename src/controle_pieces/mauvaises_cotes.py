"""Banc d'essai des mauvaises cotes.

Le fait reste vrai, seule la cote change : elle pointe vers une piece voisine
qui ne le contient pas. La passe A ne voit pas la cote, son verdict ne peut
donc pas bouger. La passe B, si.

Chaque leurre a ete verifie a la main : aucune des pieces choisies ne reprend
le fait, meme par renvoi (le dossier en contient beaucoup, voir les tests).
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass

from .chemins import ACTE_COTES, ACTE_LLM, COTES_DEPLACEES
from .piegeage import _appliquer

CITATION = re.compile(r"\(pièce n° \d+[^)]*\)")


@dataclass(frozen=True)
class Deplacement:
    erreur_id: str
    cote_correcte: int
    cote_leurre: int
    avant: str  # ancrage unique dans l'acte sain, citation comprise
    raison: str  # pourquoi ce leurre est plausible

    @property
    def apres(self) -> str:
        """Meme texte, seule la citation change."""
        return CITATION.sub(f"(pièce n° {self.cote_leurre})", self.avant)


DEPLACEMENTS: tuple[Deplacement, ...] = (
    Deplacement("M-01", 1, 2, "obligation de résultat (pièce n° 1, article 1)",
                "le bon de commande precede le contrat, mais ne le stipule pas"),
    Deplacement("M-02", 1, 9, "AXELIS (pièce n° 1)",
                "la mise en demeure vise le contrat, sans sa date ni son objet"),
    Deplacement("M-03", 1, 5, "« délais de rigueur » (pièce n° 1, article 4)",
                "le PV de recette parle des delais, pas de leur qualification"),
    Deplacement("M-04", 6, 4, "59 200 € HT (pièce n° 6)",
                "confusion entre les deux factures"),
    Deplacement("M-05", 9, 8, "14 février 2025 (pièce n° 9)",
                "le courrier de contestation precede la relance"),
    Deplacement("M-06", 5, 6, "quatre réserves bloquantes (pièce n° 5)",
                "la facture du lot 2 suit le PV, sans reprendre les reserves"),
    Deplacement("M-07", 1, 4, "lot correspondant » (pièce n° 1)",
                "la clause est citee sous la facture qu'elle encadre"),
    Deplacement("M-08", 7, 6, "n’ont pas été levées à ce jour (pièce n° 7, message 6)",
                "la facture du lot 2 est contemporaine du courriel"),
    Deplacement("M-09", 8, 6, "2 368 € (pièce n° 8)",
                "les penalites portent sur le lot 2, que cette facture concerne"),
    Deplacement("M-10", 1, 9, "dues au Prestataire » (pièce n° 1, article 8)",
                "la mise en demeure evoque les penalites, pas la clause"),
    Deplacement("M-11", 7, 3, "ne valaient pas commande (pièce n° 7, message 3)",
                "le projet d'avenant evoque les ateliers, pas le rappel du client"),
    Deplacement("M-12", 7, 3, "le 20 septembre 2024 (pièce n° 7, message 5)",
                "le refus porte sur l'avenant, mais n'y figure pas"),
    Deplacement("M-13", 3, 1, "projet non signé (pièce n° 3)",
                "le contrat prevoit l'avenant, mais ne dit rien de celui-ci"),
    Deplacement("M-14", 1, 9, "ne valent pas avenant » (pièce n° 1, article 12)",
                "la mise en demeure ne cite pas l'article 12"),
)


def spans() -> dict[str, tuple[int, int]]:
    """Position de chaque deplacement dans l'acte modifie."""
    return _appliquer(ACTE_LLM.read_text(encoding="utf-8"), DEPLACEMENTS)[1]


def construire(*, ecrire: bool = True) -> tuple[str, list[dict]]:
    acte = ACTE_LLM.read_text(encoding="utf-8")
    for d in DEPLACEMENTS:
        if acte.count(d.avant) != 1:
            raise ValueError(f"{d.erreur_id} : ancrage absent ou ambigu")

    modifie, _ = _appliquer(acte, DEPLACEMENTS)
    journal = {
        "acte_source": ACTE_LLM.name,
        "commentaire": (
            "Faits vrais deplaces sous une mauvaise cote. Seule la citation "
            "change : le texte juge en passe A est identique a l'acte sain."
        ),
        "nombre": len(DEPLACEMENTS),
        "deplacements": [asdict(d) | {"apres": d.apres} for d in DEPLACEMENTS],
    }
    if ecrire:
        ACTE_COTES.write_text(modifie, encoding="utf-8")
        COTES_DEPLACEES.write_text(
            json.dumps(journal, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    return modifie, journal["deplacements"]


def deplacement_du_segment(debut: int, fin: int) -> Deplacement | None:
    for erreur_id, (d, f) in spans().items():
        if d < fin and debut < f:
            return next(x for x in DEPLACEMENTS if x.erreur_id == erreur_id)
    return None
