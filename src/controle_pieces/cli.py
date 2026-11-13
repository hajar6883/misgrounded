"""Ligne de commande.

`python -m controle_pieces run` rejoue tout hors ligne depuis le cache commite.
Les sous-commandes qui appellent le modele sont separees et explicites.
"""

from __future__ import annotations

import argparse
import json
import sys

from . import judge, mauvaises_cotes, piegeage, redaction, report, resumes
from .chemins import ACTE_COTES, ACTE_LLM, ACTE_PIEGE, RESULTATS
from .extract import extraire


def _cmd_run(args) -> int:
    """Le pipeline complet, hors ligne, plus le rapport."""
    rapport = report.rapport_complet()
    report.ecrire(rapport)
    print(report.tableaux(rapport))
    print(f"\nDétail complet : {RESULTATS / 'resultats.json'}")
    if not rapport["dossier_piege"]["juge_a_tourne"]:
        print(
            "\nNote : la double passe A/B n'a pas encore tourné "
            "(`python -m controle_pieces juge`). Les sections 1, 2, 4 et 5 sont "
            "complètes ; seule la section 3 manque."
        )
    return 0


def _cmd_rapport(args) -> int:
    rapport = report.rapport_complet()
    if args.json:
        print(json.dumps(rapport, ensure_ascii=False, indent=2))
    else:
        print(report.tableaux(rapport))
    return 0


def _cmd_acte(args) -> int:
    acte = redaction.generer_acte()
    print(f"{ACTE_LLM} — {len(acte.split())} mots")
    return 0


def _cmd_piege(args) -> int:
    piege, erreurs = piegeage.construire()
    print(f"{ACTE_PIEGE} — {len(erreurs)} erreurs plantées")
    return 0


def _cmd_cotes(args) -> int:
    _, deplacements = mauvaises_cotes.construire()
    print(f"{ACTE_COTES} — {len(deplacements)} cotes déplacées")
    return 0


def _cmd_resumes(args) -> int:
    generes = resumes.generer_tous(trace=True)
    controles = resumes.controler_tous()
    contredites = sum(len(c.contredites) for c in controles)
    print(f"\n{len(generes)} résumés, {contredites} valeur(s) contredite(s)")
    return 0


def _cmd_juge(args) -> int:
    """La double passe. Seule sous-commande vraiment coûteuse."""
    cibles = [("piege", ACTE_PIEGE), ("genere", ACTE_LLM), ("cotes", ACTE_COTES)]
    if args.acte:
        cibles = [c for c in cibles if c[0] == args.acte]

    for nom, chemin in cibles:
        affirmations = extraire(chemin.read_text(encoding="utf-8"))
        if args.limite:
            affirmations = affirmations[: args.limite]
        print(f"\n===== acte {nom} : {len(affirmations)} affirmations =====")
        comparaisons = judge.double_passe(affirmations, trace=True)

        RESULTATS.mkdir(parents=True, exist_ok=True)
        sortie = {
            "acte": chemin.name,
            "modele_juge": judge.MODELE_JUGE,
            "synthese": judge.synthese(comparaisons),
            "comparaisons": [
                {
                    "claim_id": c.claim_id,
                    "cote_citee": c.cote_citee,
                    "texte": c.texte,
                    "valeur_brute": c.valeur_brute,
                    "classement": c.classement,
                    "passe_A": vars(c.a),
                    "passe_B": vars(c.b),
                }
                for c in comparaisons
            ],
        }
        (RESULTATS / f"double_passe_{nom}.json").write_text(
            json.dumps(sortie, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(json.dumps(sortie["synthese"], ensure_ascii=False, indent=2))
    return 0


def _cmd_renumerotation(args) -> int:
    rapport = report.rapport_renumerotation()
    print(json.dumps(rapport, ensure_ascii=False, indent=2))
    return 0


def construire_parseur() -> argparse.ArgumentParser:
    parseur = argparse.ArgumentParser(
        prog="python -m controle_pieces",
        description="Contrôle de l'ancrage factuel d'un acte sur les pièces qu'il cite.",
    )
    sous = parseur.add_subparsers(dest="commande", required=True)

    sous.add_parser("run", help="pipeline complet hors ligne + rapport").set_defaults(
        fonction=_cmd_run
    )

    p = sous.add_parser("rapport", help="affiche les métriques")
    p.add_argument("--json", action="store_true", help="sortie JSON brute")
    p.set_defaults(fonction=_cmd_rapport)

    sous.add_parser("acte", help="génère l'acte (appelle le modèle)").set_defaults(
        fonction=_cmd_acte
    )
    sous.add_parser("piege", help="construit l'acte piégé (hors ligne)").set_defaults(
        fonction=_cmd_piege
    )
    sous.add_parser("cotes", help="construit l'acte aux cotes déplacées (hors ligne)").set_defaults(
        fonction=_cmd_cotes
    )
    sous.add_parser("resumes", help="génère et vérifie les résumés").set_defaults(
        fonction=_cmd_resumes
    )

    p = sous.add_parser("juge", help="double passe A/B (appelle le modèle)")
    p.add_argument("--acte", choices=("piege", "genere", "cotes"), help="n'en traiter qu'un")
    p.add_argument("--limite", type=int, help="ne juger que les N premières")
    p.set_defaults(fonction=_cmd_juge)

    sous.add_parser("renumerotation", help="dérive naïve vs identifiant stable").set_defaults(
        fonction=_cmd_renumerotation
    )
    return parseur


def main(argv: list[str] | None = None) -> int:
    args = construire_parseur().parse_args(argv)
    return args.fonction(args)


if __name__ == "__main__":
    sys.exit(main())
