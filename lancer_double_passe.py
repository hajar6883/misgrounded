"""Lance la double passe sur les deux actes et ecrit les resultats.

Script de run, pas de bibliotheque : il sera remplace par `cli.py`.
"""
import json
import sys
import time
from dataclasses import asdict

sys.path.insert(0, "src")

from controle_pieces import judge
from controle_pieces.chemins import ACTE_LLM, ACTE_PIEGE, RESULTATS
from controle_pieces.extract import extraire

RESULTATS.mkdir(parents=True, exist_ok=True)

for nom, chemin in [("piege", ACTE_PIEGE), ("genere", ACTE_LLM)]:
    debut = time.time()
    print(f"\n===== acte {nom} =====", flush=True)
    affirmations = extraire(chemin.read_text(encoding="utf-8"))
    comparaisons = judge.double_passe(affirmations, trace=True)

    sortie = {
        "acte": chemin.name,
        "modele_juge": judge.MODELE_JUGE,
        "duree_s": round(time.time() - debut, 1),
        "synthese": judge.synthese(comparaisons),
        "comparaisons": [
            {
                "claim_id": c.claim_id,
                "cote_citee": c.cote_citee,
                "texte": c.texte,
                "valeur_brute": c.valeur_brute,
                "classement": c.classement,
                "passe_A": asdict(c.a),
                "passe_B": asdict(c.b),
            }
            for c in comparaisons
        ],
    }
    fichier = RESULTATS / f"double_passe_{nom}.json"
    fichier.write_text(json.dumps(sortie, ensure_ascii=False, indent=2) + "\n",
                       encoding="utf-8")
    print(f"\n--- {nom} : {json.dumps(sortie['synthese'], ensure_ascii=False)}", flush=True)
    print(f"--- ecrit dans {fichier}", flush=True)
