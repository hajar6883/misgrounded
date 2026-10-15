"""Le dossier fictif est une fixture : on le teste comme du code.

Une fixture incoherente rendrait toutes les metriques ininterpretables.
"""

from __future__ import annotations

import re
from decimal import Decimal

import pytest

from conftest import (
    MOIS,
    cle_tva_francaise,
    en_decimal,
    est_montant,
    lignes_de_detail,
    lignes_tableau,
    luhn_valide,
    normaliser_espaces,
    totaux,
)

TVA = Decimal("0.20")

# --- Identifiants d'entreprise ------------------------------------------------

RCS = re.compile(r"RCS Lyon (\d{3} \d{3} \d{3})")
SIRET = re.compile(r"SIRET (\d{3} \d{3} \d{3} \d{5})")
TVA_INTRA = re.compile(r"FR (\d{2}) (\d{3} \d{3} \d{3})")


def test_les_siren_ont_une_cle_de_luhn_valide(pieces):
    """Un SIREN invente au hasard a 90 % de chances d'etre invalide."""
    vus = set()
    for nom, texte in pieces.items():
        for siren in RCS.findall(texte):
            vus.add(siren)
            assert luhn_valide(siren), f"{nom} : SIREN {siren} invalide"
    assert vus, "aucun SIREN trouve dans le dossier"


def test_les_siret_ont_une_cle_de_luhn_valide(pieces):
    for nom, texte in pieces.items():
        for siret in SIRET.findall(texte):
            assert luhn_valide(siret), f"{nom} : SIRET {siret} invalide"


def test_les_numeros_de_tva_derivent_bien_du_siren(pieces):
    for nom, texte in pieces.items():
        for cle, siren in TVA_INTRA.findall(texte):
            attendue = cle_tva_francaise(siren.replace(" ", ""))
            assert int(cle) == attendue, (
                f"{nom} : TVA FR {cle} {siren} — cle attendue {attendue:02d}"
            )


def test_le_siret_prolonge_le_siren_de_la_meme_societe(pieces):
    for nom, texte in pieces.items():
        for siret in SIRET.findall(texte):
            siren = siret[:11]
            assert siren in RCS.findall(texte), (
                f"{nom} : SIRET {siret} ne correspond a aucun SIREN de la piece"
            )


# --- Arithmetique des pieces comptables ---------------------------------------


def test_ht_tva_ttc_sont_coherents(pieces):
    testees = 0
    for nom, texte in pieces.items():
        t = totaux(texte)
        if not {"ht", "tva", "ttc"} <= t.keys():
            continue
        testees += 1
        assert t["tva"] == t["ht"] * TVA, f"{nom} : TVA != 20 % du HT"
        assert t["ttc"] == t["ht"] + t["tva"], f"{nom} : TTC != HT + TVA"
    assert testees >= 3, f"seulement {testees} pieces comptables testees"


def test_les_lignes_de_detail_somment_au_total_ht(pieces):
    for nom, texte in pieces.items():
        t = totaux(texte)
        if "ht" not in t:
            continue
        lignes = lignes_de_detail(texte)
        if not lignes:
            continue
        # Le bon de commande porte aussi des prix unitaires : on ne retient que
        # la derniere colonne, deja filtree par lignes_de_detail().
        assert sum(lignes) == t["ht"], (
            f"{nom} : somme des lignes {sum(lignes)} != total HT {t['ht']}"
        )


# --- Coherence du contrat -----------------------------------------------------

FORFAIT = Decimal("148000")
LOTS = {
    "lot 1": Decimal("44400"),
    "lot 2": Decimal("59200"),
    "lot 3": Decimal("44400"),
}


def test_le_forfait_egale_la_somme_des_trois_lots():
    assert sum(LOTS.values()) == FORFAIT


def test_le_contrat_annonce_bien_le_forfait_en_chiffres_et_en_lettres(pieces):
    contrat = normaliser_espaces(pieces["P01_contrat_prestation.md"])
    assert "148 000 € HT" in contrat
    assert "cent quarante-huit mille euros hors taxes" in contrat
    assert "177 600 € TTC" in contrat
    assert en_decimal("177 600,00 €") == FORFAIT * (1 + TVA)


def test_chaque_lot_est_facture_pour_son_montant_contractuel(pieces):
    factures = {
        "P04_facture_F2024_0412.md": LOTS["lot 1"],
        "P06_facture_F2024_0731.md": LOTS["lot 2"],
    }
    for nom, attendu in factures.items():
        assert totaux(pieces[nom])["ht"] == attendu, f"{nom} : montant hors contrat"


# --- La clause penale, qui decide du litige -----------------------------------


def test_penalites_du_lot_2_conformes_a_l_article_8(pieces):
    """0,5 % par semaine entamee, plafonnees a 10 % du lot."""
    lot2 = LOTS["lot 2"]
    hebdomadaire = lot2 * Decimal("0.005")
    plafond = lot2 * Decimal("0.10")

    assert hebdomadaire == Decimal("296.000")
    assert plafond == Decimal("5920.00")
    # Le plafond n'est atteint qu'au bout de 20 semaines, soit le 7 mars 2025 :
    # aucune date du dossier ne l'atteint, le calcul reste donc non trivial.
    assert plafond / hebdomadaire == 20


# --- Le piege central : l'avenant n'a jamais ete signe -------------------------


def test_l_avenant_reste_un_projet_non_signe(pieces):
    avenant = normaliser_espaces(pieces["P03_projet_avenant_non_signe.md"])
    assert "PROJET" in avenant
    assert "non renseignée" in avenant, "les zones de signature doivent rester vides"
    assert "Sans retour signé à ce jour" in avenant
    # Un avenant signe reporterait le lot 2 et annulerait les penalites :
    # c'est exactement le fait qu'un LLM peut halluciner.
    assert "29 novembre 2024" in avenant


def test_le_contrat_exige_un_avenant_ecrit(pieces):
    contrat = normaliser_espaces(pieces["P01_contrat_prestation.md"])
    assert "avenant écrit, signé des deux Parties" in contrat
    assert "ne valent pas avenant" in contrat


# --- Coherence du proces-verbal de recette ------------------------------------


def test_le_pv_compte_bien_douze_reserves_dont_quatre_bloquantes(pieces):
    pv = pieces["P05_pv_recette_reserves.md"]
    reserves = set(re.findall(r"R-(\d{2})", pv))
    assert len(reserves) == 12, f"{len(reserves)} reserves distinctes au lieu de 12"
    bloquantes = {"01", "02", "03", "04"}
    assert bloquantes <= reserves
    assert "douze (12) réserves" in normaliser_espaces(pv)
    assert "quatre (4) qualifiées de bloquantes" in normaliser_espaces(pv)


def test_les_cas_de_test_du_pv_somment_au_total(pieces):
    pv = normaliser_espaces(pieces["P05_pv_recette_reserves.md"])
    conformes = int(re.search(r"\| Conformes \| (\d+) \|", pv).group(1))
    non_conformes = int(re.search(r"\| Non conformes \| (\d+) \|", pv).group(1))
    total = int(re.search(r"\| \*\*Total\*\* \| \*\*(\d+)\*\* \|", pv).group(1))
    assert conformes + non_conformes == total == 148
    # Une reserve par cas non conforme : le compte doit tomber juste.
    assert non_conformes == 12


# --- Chronologie --------------------------------------------------------------

DATE_FR = re.compile(
    r"\b(\d{1,2}) (janvier|février|mars|avril|mai|juin|juillet|août|"
    r"septembre|octobre|novembre|décembre) (20\d{2})\b"
)


def _dates(texte: str) -> set[tuple[int, int, int]]:
    return {
        (int(a), MOIS[m], int(j))
        for j, m, a in DATE_FR.findall(normaliser_espaces(texte))
    }


@pytest.mark.parametrize(
    "fichier, plus_tot",
    [
        ("P02_bon_de_commande.md", (2024, 3, 6)),
        ("P01_contrat_prestation.md", (2024, 3, 6)),
        ("P04_facture_F2024_0412.md", (2024, 4, 2)),
        ("P05_pv_recette_reserves.md", (2024, 4, 2)),
        ("P06_facture_F2024_0731.md", (2024, 4, 2)),
        ("P07_fil_courriels.md", (2024, 4, 2)),
        ("P08_courrier_contestation.md", (2024, 4, 2)),
        ("P09_mise_en_demeure.md", (2024, 4, 2)),
        # P10 est exclu : le Kbis porte la date d'immatriculation de 2020,
        # anterieure au dossier par construction.
    ],
)
def test_aucune_date_anterieure_au_debut_du_dossier(pieces, fichier, plus_tot):
    """Rien ne peut preceder la proposition du 6 mars 2024."""
    for date in _dates(pieces[fichier]):
        assert date >= plus_tot, f"{fichier} : date {date} anterieure a {plus_tot}"


def test_les_echeances_de_facture_sont_a_trente_jours(pieces):
    """L'article 6 du contrat impose un reglement a 30 jours date de facture."""
    attendu = {
        "P04_facture_F2024_0412.md": ((2024, 6, 30), (2024, 7, 30)),
        "P06_facture_F2024_0731.md": ((2024, 11, 21), (2024, 12, 21)),
    }
    from datetime import date

    for fichier, (emission, echeance) in attendu.items():
        presentes = _dates(pieces[fichier])
        assert emission in presentes, f"{fichier} : date d'emission absente"
        assert echeance in presentes, f"{fichier} : date d'echeance absente"
        assert (date(*echeance) - date(*emission)).days == 30


# --- Coherence des courriers et courriels -------------------------------------

JOURS = "lundi mardi mercredi jeudi vendredi samedi dimanche".split()
ENTETE_DATE = re.compile(
    r"\*\*Date :\*\* (\w+) (\d{1,2}) (\w+) (20\d{2}), (\d{2}) h (\d{2})"
)


def test_les_jours_de_la_semaine_des_courriels_sont_exacts(pieces):
    """Un courriel date « jeudi 27 juin 2024 » doit vraiment tomber un jeudi."""
    from datetime import date

    fil = normaliser_espaces(pieces["P07_fil_courriels.md"])
    entetes = ENTETE_DATE.findall(fil)
    assert len(entetes) == 6, f"{len(entetes)} courriels dates au lieu de 6"
    for jour, j, mois, annee, _, _ in entetes:
        reel = JOURS[date(int(annee), MOIS[mois], int(j)).weekday()]
        assert jour == reel, f"{j} {mois} {annee} est un {reel}, pas un {jour}"


def test_les_courriels_sont_en_ordre_chronologique(pieces):
    from datetime import date

    fil = normaliser_espaces(pieces["P07_fil_courriels.md"])
    dates = [
        date(int(a), MOIS[m], int(j))
        for _, j, m, a, _, _ in ENTETE_DATE.findall(fil)
    ]
    assert dates == sorted(dates), "le fil de courriels n'est pas chronologique"


def test_le_calcul_des_penalites_du_courrier_de_contestation(pieces):
    """La contestation du 9 decembre 2024 doit tomber sur 2 368 euros."""
    from datetime import date

    lettre = normaliser_espaces(pieces["P08_courrier_contestation.md"])
    retard = (date(2024, 12, 9) - date(2024, 10, 18)).days
    semaines = -(-retard // 7)  # semaines entamees, arrondi superieur
    penalites = LOTS["lot 2"] * Decimal("0.005") * semaines

    assert retard == 52 and semaines == 8
    assert penalites == Decimal("2368.000")
    assert f"{retard} jours, soit {semaines} semaines entamées" in lettre
    assert "2 368,00 €" in lettre
    assert "296,00 €" in lettre
    assert "5 920,00 €" in lettre  # le plafond, rappele mais pas atteint


def test_le_total_reclame_par_la_mise_en_demeure(pieces):
    """71 040 € de facture + 40 € d'indemnite forfaitaire = 71 080 €."""
    lettre = normaliser_espaces(pieces["P09_mise_en_demeure.md"])
    postes: dict[str, Decimal] = {}
    for cellules in lignes_tableau(lettre):
        if len(cellules) < 2 or not est_montant(cellules[-1]):
            continue
        libelle = cellules[0].replace("*", "").strip().lower()
        for cle in ("facture", "indemnité", "total"):
            if libelle.startswith(cle):
                postes[cle] = en_decimal(cellules[-1])

    assert postes.keys() == {"facture", "indemnité", "total"}
    assert postes["facture"] == Decimal("71040.00")
    assert postes["indemnité"] == Decimal("40.00")
    assert postes["facture"] + postes["indemnité"] == postes["total"]
    assert postes["total"] == Decimal("71080.00")


def test_l_echeance_de_la_mise_en_demeure_est_coherente(pieces):
    """15 jours a compter de la reception du 29 janvier 2025 -> 13 fevrier 2025."""
    from datetime import date, timedelta

    lettre = normaliser_espaces(pieces["P09_mise_en_demeure.md"])
    assert "29 janvier 2025" in lettre
    assert (date(2025, 1, 29) + timedelta(days=15)) == date(2025, 2, 13)
    assert "expiré depuis le 13 février 2025" in lettre


# --- Les reserves racontent la meme histoire dans trois pieces -----------------


def test_les_reserves_non_levees_sont_les_memes_partout(pieces):
    """P05 les consigne, P07 les reconnait non levees, P08 s'en prevaut."""
    pv = normaliser_espaces(pieces["P05_pv_recette_reserves.md"])
    courriels = normaliser_espaces(pieces["P07_fil_courriels.md"])
    contestation = normaliser_espaces(pieces["P08_courrier_contestation.md"])

    # Les quatre bloquantes sont bien celles du PV.
    for reserve in ("R-01", "R-02", "R-03", "R-04"):
        assert reserve in pv

    # L'aveu du prestataire : R-02 et R-04 restent non levees.
    assert "**Non levées :**" in courriels
    non_levees = courriels.split("**Non levées :**")[1].split("\n\n")[0]
    assert "R-02" in non_levees and "R-04" in non_levees
    assert "R-01" not in non_levees and "R-03" not in non_levees

    # Le client s'en prevaut, et seulement de celles-la.
    assert "réserves **R-02** et **R-04** demeurent non levées" in contestation


# --- Le Kbis doit decrire la meme societe que le contrat -----------------------


def test_le_kbis_decrit_bien_le_prestataire(pieces):
    kbis = normaliser_espaces(pieces["P10_extrait_kbis_altimeo.md"])
    contrat = normaliser_espaces(pieces["P01_contrat_prestation.md"])

    for mention in (
        "ALTIMEO CONSEIL",
        "891 204 331",
        "25 000,00 euros",
        "14 rue Frédéric Mistral",
        "FERRAND Samuel",
    ):
        assert mention in kbis, f"mention absente du Kbis : {mention}"

    # Le capital et le siege doivent concorder avec l'en-tete du contrat.
    assert "capital de 25 000 euros" in contrat
    assert "14 rue Frédéric Mistral" in contrat


def test_le_kbis_ne_mentionne_aucune_procedure_collective(pieces):
    """Une societe en liquidation changerait tout l'enjeu du litige."""
    kbis = pieces["P10_extrait_kbis_altimeo.md"]
    assert "aucune mention de procédure collective" in normaliser_espaces(kbis)
