"""Metriques et tableaux. Tous les chiffres du README sortent d'ici.

Les deux actes ne sont jamais agreges : le piege mesure le rappel sur des
erreurs connues, le genere ne peut produire que des candidats a relire.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass

from . import piegeage, renumber, resumes
from .checks import controler
from .chemins import ACTE_LLM, ACTE_PIEGE, RESULTATS
from .dossier import par_cote
from .extract import Affirmation, extraire
from .locate import localiser


@dataclass(frozen=True)
class Alerte:
    """Une affirmation sur laquelle au moins une couche a leve un doute."""

    claim_id: str
    cote_citee: int
    valeur_brute: str | None
    source: str  # deterministe | localisation | juge
    classement: str
    erreur_plantee: str | None


def _taux(numerateur: int, denominateur: int) -> float:
    return round(numerateur / denominateur, 4) if denominateur else 0.0


def _verdicts_du_juge(nom: str) -> dict[str, dict]:
    """Charge la double passe si elle a deja tourne, sinon renvoie vide."""
    fichier = RESULTATS / f"double_passe_{nom}.json"
    if not fichier.exists():
        return {}
    brut = json.loads(fichier.read_text(encoding="utf-8"))
    return {c["claim_id"]: c for c in brut["comparaisons"]}


def analyser_acte(nom: str, chemin) -> dict:
    """Passe les trois couches sur un acte et rassemble les alertes."""
    pieces = par_cote()
    affirmations: list[Affirmation] = extraire(chemin.read_text(encoding="utf-8"))
    juge = _verdicts_du_juge(nom)

    alertes: list[Alerte] = []
    confirmees_deterministe = 0

    for a in affirmations:
        erreur = piegeage.erreur_du_segment(a.debut, a.fin)
        ref = erreur.erreur_id if erreur else None

        # Couche 1 : controle deterministe des valeurs.
        if a.porte_une_valeur and a.valeur is not None:
            verdict = controler(a.valeur, pieces[a.cote_citee].texte)
            if verdict.verdict == "contredit":
                alertes.append(Alerte(a.claim_id, a.cote_citee, a.valeur_brute,
                                      "deterministe", "contredit", ref))
                continue
            if verdict.verdict == "confirme":
                confirmees_deterministe += 1
                continue

        # Couche 2 : localisation dans le reste du dossier.
        loc = localiser(a)
        if loc.classement in ("mauvaise_cote", "non_etaye"):
            alertes.append(Alerte(a.claim_id, a.cote_citee, a.valeur_brute,
                                  "localisation", loc.classement, ref))
            continue

        # Couche 3 : le juge, sur ce que les regles n'ont pas tranche.
        comparaison = juge.get(a.claim_id)
        if comparaison and comparaison["classement"] in ("misgrounded", "non_etaye"):
            alertes.append(Alerte(a.claim_id, a.cote_citee, a.valeur_brute,
                                  "juge", comparaison["classement"], ref))

    rapport = {
        "acte": chemin.name,
        "affirmations": len(affirmations),
        "confirmees_par_les_regles": confirmees_deterministe,
        "alertes": len(alertes),
        "alertes_par_source": dict(Counter(a.source for a in alertes)),
        "alertes_par_classement": dict(Counter(a.classement for a in alertes)),
        "juge_a_tourne": bool(juge),
        "detail": [vars(a) for a in alertes],
    }

    if juge:
        classements = Counter(c["classement"] for c in juge.values())
        rapport["double_passe"] = {
            "classements": dict(classements),
            "taux_misgrounded": _taux(classements["misgrounded"], len(juge)),
            "taux_non_etaye": _taux(classements["non_etaye"], len(juge)),
            "incoherences_du_juge": classements["incoherence_du_juge"],
        }
    return rapport


def rapport_dossier_piege() -> dict:
    """Rappel et fausses alertes : les deux sont definis sans ambiguite ici."""
    base = analyser_acte("piege", ACTE_PIEGE)
    plantees = {e.erreur_id for e in piegeage.ERREURS}

    detectees = {a["erreur_plantee"] for a in base["detail"] if a["erreur_plantee"]}
    fausses = [a for a in base["detail"] if not a["erreur_plantee"]]
    saines = base["affirmations"] - len(
        {a["claim_id"] for a in base["detail"] if a["erreur_plantee"]}
    )

    base["erreurs_plantees"] = len(plantees)
    base["erreurs_detectees"] = len(detectees)
    base["erreurs_manquees"] = sorted(plantees - detectees)
    base["rappel_verificateur"] = _taux(len(detectees), len(plantees))
    base["fausses_alertes"] = len(fausses)
    base["taux_fausses_alertes"] = _taux(len(fausses), saines)
    return base


def rapport_acte_genere() -> dict:
    """Pas de verite terrain ici : les alertes sont des candidats a relire."""
    base = analyser_acte("genere", ACTE_LLM)
    base["erreurs_naturelles_candidates"] = base["alertes"]
    base["note"] = (
        "Aucune verite terrain affirmation par affirmation sur cet acte : les "
        "alertes sont des erreurs naturelles candidates, a relire, et non des "
        "fausses alertes."
    )
    return base


def rapport_renumerotation() -> dict:
    return renumber.comparer(ACTE_LLM.read_text(encoding="utf-8"))


def rapport_resumes() -> dict:
    controles = resumes.controler_tous()
    valeurs = sum(c.valeurs for c in controles)
    return {
        "resumes": len(controles),
        "valeurs_chiffrees": valeurs,
        "confirmees": sum(c.confirmees for c in controles),
        "contredites": sum(len(c.contredites) for c in controles),
        "indecidables": sum(c.indecidables for c in controles),
        "taux_confirme": _taux(sum(c.confirmees for c in controles), valeurs),
    }


def rapport_complet() -> dict:
    return {
        "dossier_piege": rapport_dossier_piege(),
        "acte_genere": rapport_acte_genere(),
        "renumerotation": rapport_renumerotation(),
        "resumes_du_bordereau": rapport_resumes(),
    }


def ecrire(rapport: dict) -> None:
    RESULTATS.mkdir(parents=True, exist_ok=True)
    (RESULTATS / "resultats.json").write_text(
        json.dumps(rapport, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


# --- Rendu lisible ---------------------------------------------------------


def tableaux(rapport: dict) -> str:
    p, g = rapport["dossier_piege"], rapport["acte_genere"]
    r, s = rapport["renumerotation"], rapport["resumes_du_bordereau"]
    lignes = []

    lignes += [
        "### 1. Dossier piégé — rappel et fausses alertes",
        "",
        "*Les erreurs sont plantées et connues : les deux métriques sont exactes.*",
        "",
        "| Métrique | Valeur |",
        "|---|---|",
        f"| Affirmations extraites | {p['affirmations']} |",
        f"| Erreurs plantées | {p['erreurs_plantees']} |",
        f"| Erreurs détectées | {p['erreurs_detectees']} |",
        f"| **Rappel du vérificateur** | **{p['rappel_verificateur']:.0%}** |",
        f"| Fausses alertes | {p['fausses_alertes']} |",
        f"| **Taux de fausses alertes** | **{p['taux_fausses_alertes']:.0%}** |",
    ]
    if p["erreurs_manquees"]:
        lignes.append(f"| Erreurs manquées | {', '.join(p['erreurs_manquees'])} |")

    lignes += [
        "",
        "### 2. Acte réellement généré — erreurs naturelles",
        "",
        "*Aucune erreur injectée : les alertes sont des candidats à relire.*",
        "",
        "| Métrique | Valeur |",
        "|---|---|",
        f"| Affirmations extraites | {g['affirmations']} |",
        f"| Confirmées par les règles | {g['confirmees_par_les_regles']} |",
        f"| Erreurs naturelles candidates | {g['erreurs_naturelles_candidates']} |",
    ]

    for titre, source in (("dossier piégé", p), ("acte généré", g)):
        if "double_passe" in source:
            d = source["double_passe"]
            lignes += [
                "",
                f"### 3. Double passe A/B — {titre}",
                "",
                "| Classement | Nombre |",
                "|---|---|",
            ]
            for k, v in sorted(d["classements"].items()):
                lignes.append(f"| `{k}` | {v} |")
            lignes.append(f"| **Taux misgrounded** | **{d['taux_misgrounded']:.0%}** |")

    lignes += [
        "",
        "### 4. Dérive de renumérotation",
        "",
        "| Version | Citations cassées | Taux |",
        "|---|---|---|",
        f"| Naïve (cote écrite en dur) | {r['naif']['citations_cassees']} / "
        f"{r['citations_dans_l_acte']} | {r['naif']['taux']:.0%} |",
        f"| **Identifiant stable** | **{r['identifiant_stable']['citations_cassees']} / "
        f"{r['citations_dans_l_acte']}** | **{r['identifiant_stable']['taux']:.0%}** |",
        "",
        "### 5. Résumés du bordereau",
        "",
        "| Métrique | Valeur |",
        "|---|---|",
        f"| Résumés générés | {s['resumes']} |",
        f"| Valeurs chiffrées | {s['valeurs_chiffrees']} |",
        f"| Confirmées | {s['confirmees']} |",
        f"| Contredites | {s['contredites']} |",
    ]
    return "\n".join(lignes)
