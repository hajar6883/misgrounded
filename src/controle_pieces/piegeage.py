"""Construction du dossier piege.

Les erreurs sont des substitutions declarees, sans LLM : reproductibles a
l'identique. La construction echoue si un ancrage n'apparait pas exactement
une fois dans l'acte source.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass

from .chemins import ACTE_LLM, ACTE_PIEGE, ERREURS_PLANTEES


@dataclass(frozen=True)
class ErreurPlantee:
    erreur_id: str
    categorie: str
    cote_citee: int
    verdict_attendu: str
    classement_attendu: str
    avant: str
    apres: str
    explication: str


# Les 12 erreurs. Chacune vise un mode d'echec distinct, pour que le rappel
# soit lisible par categorie et pas seulement en agrege.
ERREURS: tuple[ErreurPlantee, ...] = (
    ErreurPlantee(
        erreur_id="E-01",
        categorie="montant_faux",
        cote_citee=8,
        verdict_attendu="contredit",
        classement_attendu="non_etaye",
        avant="hauteur de 2 368 € (pièce n° 8)",
        apres="hauteur de 4 440 € (pièce n° 8)",
        explication=(
            "4 440 € est le montant des penalites au 27 janvier 2025, pas au "
            "9 decembre 2024. Le chiffre est juridiquement correct a une autre "
            "date, mais absent de la piece citee. Piege supplementaire : il est "
            "le dixieme de 44 400 €, le montant d'un lot -- une confusion "
            "d'ordre de grandeur tres plausible."
        ),
    ),
    ErreurPlantee(
        erreur_id="E-02",
        categorie="confusion_ht_ttc",
        cote_citee=6,
        verdict_attendu="contredit",
        classement_attendu="non_etaye",
        avant="d’un montant de 59 200 € HT (pièce n° 6)",
        apres="d’un montant de 59 200 € TTC (pièce n° 6)",
        explication=(
            "La valeur est juste, la qualification ne l'est pas : 59 200 € est "
            "un montant HT, le TTC de cette facture est 71 040 €. Ce type "
            "d'erreur est invisible a la relecture rapide."
        ),
    ),
    ErreurPlantee(
        erreur_id="E-03",
        categorie="mauvaise_cote",
        cote_citee=2,
        verdict_attendu="absent",
        classement_attendu="mauvaise_cote",
        avant="(pièce n° 4 ; pièce n° 7, message 2)",
        apres="(pièce n° 2)",
        explication=(
            "Le fait est vrai : la facture du lot 1 s'eleve bien a 44 400 € HT. "
            "Mais elle est etablie par la piece n° 4, pas par le bon de commande "
            "n° 2, qui porte sur 62 400 € HT. Cas canonique de mauvaise cote."
        ),
    ),
    ErreurPlantee(
        erreur_id="E-04",
        categorie="mauvaise_cote",
        cote_citee=1,
        verdict_attendu="contredit",
        classement_attendu="mauvaise_cote",
        avant="devait être livré au plus tard le 18 octobre 2024 (pièce n° 1, article 4)",
        apres="devait être livré au plus tard le 29 novembre 2024 (pièce n° 1, article 4)",
        explication=(
            "Le 29 novembre 2024 existe dans le dossier, mais seulement dans le "
            "projet d'avenant non signe (piece n° 3). L'attribuer au contrat "
            "renverse l'issue du litige : a cette date, aucune penalite n'est "
            "due. C'est l'erreur la plus couteuse du lot."
        ),
    ),
    ErreurPlantee(
        erreur_id="E-05",
        categorie="fait_invente",
        cote_citee=3,
        verdict_attendu="contredit",
        classement_attendu="non_etaye",
        avant="est demeuré à l’état de projet non signé (pièce n° 3)",
        apres="a été signé par les deux parties le 17 septembre 2024 (pièce n° 3)",
        explication=(
            "Inversion pure et simple du fait decisif. La piece n° 3 porte la "
            "mention « Sans retour signe a ce jour » et ses zones de signature "
            "sont vides. Un juge qui valide cela n'a pas lu la piece."
        ),
    ),
    ErreurPlantee(
        erreur_id="E-06",
        categorie="montant_faux",
        cote_citee=5,
        verdict_attendu="contredit",
        classement_attendu="non_etaye",
        avant="révélé douze réserves, dont quatre",
        apres="révélé quinze réserves, dont six",
        explication=(
            "Ni quinze ni six n'apparaissent nulle part dans le dossier. Erreur "
            "de comptage sur des valeurs que le proces-verbal enonce pourtant "
            "en toutes lettres."
        ),
    ),
    ErreurPlantee(
        erreur_id="E-07",
        categorie="date_fausse",
        cote_citee=7,
        verdict_attendu="contredit",
        classement_attendu="mauvaise_cote",
        avant="réceptionné sans réserve le 27 juin 2024 (pièce n° 7, message 1)",
        apres="réceptionné sans réserve le 30 juin 2024 (pièce n° 7, message 1)",
        explication=(
            "Le 30 juin 2024 est la date d'emission de la facture (piece n° 4), "
            "pas celle de la recette. Deux dates voisines de trois jours, pour "
            "deux evenements distincts : confusion classique."
        ),
    ),
    ErreurPlantee(
        erreur_id="E-08",
        categorie="mauvaise_cote",
        cote_citee=8,
        verdict_attendu="absent",
        classement_attendu="mauvaise_cote",
        avant="(pièce n° 1, article 8)",
        apres="(pièce n° 8)",
        explication=(
            "La clause citee est celle du contrat. La piece n° 8 l'applique mais "
            "ne la stipule pas. C'est le piege construit des la redaction du "
            "dossier : une regle enoncee dans une piece, mise en oeuvre dans une "
            "autre."
        ),
    ),
    ErreurPlantee(
        erreur_id="E-09",
        categorie="montant_faux",
        cote_citee=1,
        verdict_attendu="contredit",
        classement_attendu="non_etaye",
        avant="dans la limite de 10 %",
        apres="dans la limite de 15 %",
        explication=(
            "Le plafond contractuel est de 10 %. 15 % n'existe nulle part. "
            "Erreur sur une valeur pourtant citee dans la phrase precedente."
        ),
    ),
    ErreurPlantee(
        erreur_id="E-10",
        categorie="fait_invente",
        cote_citee=7,
        verdict_attendu="contredit",
        classement_attendu="non_etaye",
        avant="et R-04 (absence de reprise de l’historique des tarifs) n’ont pas été levées",
        apres="et R-03 (échec de l’édition des bons de livraison) n’ont pas été levées",
        explication=(
            "La piece n° 7 dit exactement l'inverse : R-03 fait partie des "
            "reserves levees. Le fait est contredit par la piece meme qui est "
            "citee a son appui."
        ),
    ),
    ErreurPlantee(
        erreur_id="E-11",
        categorie="fait_invente",
        cote_citee=7,
        verdict_attendu="absent",
        classement_attendu="non_etaye",
        avant="avant d’assigner la société NOVERIA DISTRIBUTION devant votre juridiction.",
        apres=(
            "avant d’assigner la société NOVERIA DISTRIBUTION devant votre "
            "juridiction. La société ALTIMEO CONSEIL a par ailleurs reconnu, "
            "lors du comité de pilotage du 12 décembre 2024, que le module "
            "stocks demeurait inexploitable en production (pièce n° 7)."
        ),
        explication=(
            "Hallucination complete : ni ce comite de pilotage, ni cette date, "
            "ni cet aveu n'existent dans le dossier. C'est le cas le plus grave "
            "et, en principe, le plus facile a detecter."
        ),
    ),
    ErreurPlantee(
        erreur_id="E-12",
        categorie="date_fausse",
        cote_citee=9,
        verdict_attendu="contredit",
        classement_attendu="mauvaise_cote",
        avant="adresser une mise en demeure de payer le 27 janvier 2025",
        apres="adresser une mise en demeure de payer le 21 décembre 2024",
        explication=(
            "Le 21 decembre 2024 est la date d'echeance de la facture "
            "(piece n° 6), pas celle de la mise en demeure. Erreur de report "
            "d'une date reelle du dossier sur le mauvais evenement."
        ),
    ),
)


class AncrageIntrouvable(RuntimeError):
    """Un point d'ancrage n'apparait pas exactement une fois dans l'acte."""


def verifier_ancrages(acte: str) -> None:
    """Refuse de continuer si un ancrage est absent ou ambigu.

    Sans ce garde-fou, une erreur non appliquee serait comptee comme "non
    detectee" et ferait chuter le rappel pour une raison purement technique.
    """
    problemes = []
    for erreur in ERREURS:
        occurrences = acte.count(erreur.avant)
        if occurrences != 1:
            problemes.append(
                f"  {erreur.erreur_id} : {occurrences} occurrence(s) de "
                f"{erreur.avant!r}"
            )
    if problemes:
        raise AncrageIntrouvable(
            "ancrages invalides dans l'acte source :\n" + "\n".join(problemes)
        )


def _appliquer(acte: str, erreurs=ERREURS) -> tuple[str, dict[str, tuple[int, int]]]:
    """Applique les substitutions en suivant ou chacune atterrit.

    Les positions sont la seule facon exacte de rattacher une alerte a son
    erreur : chercher la valeur ou la citation apres coup produit des
    rattachements fortuits, qui gonflent le rappel et masquent les fausses
    alertes.
    """
    piege = acte
    spans: dict[str, tuple[int, int]] = {}
    for erreur in erreurs:
        i = piege.index(erreur.avant)
        piege = piege[:i] + erreur.apres + piege[i + len(erreur.avant) :]
        decalage = len(erreur.apres) - len(erreur.avant)
        spans = {
            eid: (d + decalage if d > i else d, f + decalage if f > i else f)
            for eid, (d, f) in spans.items()
        }
        spans[erreur.erreur_id] = (i, i + len(erreur.apres))
    return piege, spans


def spans() -> dict[str, tuple[int, int]]:
    """Position de chaque erreur dans l'acte piege."""
    return _appliquer(ACTE_LLM.read_text(encoding="utf-8"))[1]


def construire(*, ecrire: bool = True) -> tuple[str, list[dict]]:
    """Produit l'acte piege et la liste des erreurs plantees."""
    acte = ACTE_LLM.read_text(encoding="utf-8")
    verifier_ancrages(acte)

    piege, spans = _appliquer(acte)

    journal = {
        "acte_source": ACTE_LLM.name,
        "commentaire": (
            "Erreurs plantees volontairement dans l'acte, pour mesurer ce que "
            "le verificateur attrape (rappel) et ce qu'il signale a tort "
            "(fausses alertes). Aucune n'est produite par un modele : ce sont "
            "des substitutions deterministes."
        ),
        "nombre": len(ERREURS),
        "erreurs": [asdict(e) for e in ERREURS],
    }

    if ecrire:
        ACTE_PIEGE.write_text(piege, encoding="utf-8")
        ERREURS_PLANTEES.write_text(
            json.dumps(journal, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return piege, journal["erreurs"]


def erreur_du_segment(debut: int, fin: int) -> ErreurPlantee | None:
    """L'erreur plantee dont la substitution tombe dans ce segment de l'acte.

    Un chevauchement de positions ne se discute pas : ni la valeur ni la
    citation n'entrent en jeu.
    """
    for erreur_id, (d, f) in spans().items():
        if d < fin and debut < f:
            return next(e for e in ERREURS if e.erreur_id == erreur_id)
    return None
