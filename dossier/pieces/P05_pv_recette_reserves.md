# PROCÈS-VERBAL DE RECETTE — LOT 2

**Projet AXELIS — Déploiement des modules gestion commerciale et stocks**
Contrat de prestation de services du 2 avril 2024, article 9

---

|  |  |
|---|---|
| **Date des opérations de recette** | du 14 au 18 octobre 2024 |
| **Date du présent procès-verbal** | 18 octobre 2024 |
| **Lieu** | Lyon, siège de NOVERIA DISTRIBUTION |

**Présents**

| Nom | Société | Qualité |
|---|---|---|
| Julien BRESSAND | NOVERIA DISTRIBUTION | Responsable des systèmes d'information |
| Sophie MERCIER | NOVERIA DISTRIBUTION | Responsable administration des ventes |
| Karim BENALI | ALTIMEO CONSEIL | Chef de projet |
| Élodie VASSEUR | ALTIMEO CONSEIL | Consultante fonctionnelle |

---

## 1. Objet

Les Parties se sont réunies aux fins de procéder à la recette du lot 2, conformément à l'article 9 du contrat.

Les opérations ont porté sur 148 cas de test issus du cahier de recette validé en comité de pilotage du 3 septembre 2024.

## 2. Résultat des tests

| Résultat | Nombre de cas |
|---|---|
| Conformes | 136 |
| Non conformes | 12 |
| **Total** | **148** |

## 3. Réserves

Les Parties consignent **douze (12) réserves**, dont **quatre (4) qualifiées de bloquantes** au sens de l'article 9 du contrat.

### 3.1 Réserves bloquantes

| N° | Description | Impact |
|---|---|---|
| R-01 | Le calcul de la remise par palier ne s'applique pas aux commandes multi-lignes : les remises sont sous-évaluées jusqu'à 12 % | Facturation client erronée — exploitation impossible |
| R-02 | Les mouvements de stock ne sont pas décrémentés lors des livraisons partielles | Stock théorique faux dès la première journée d'exploitation |
| R-03 | L'édition des bons de livraison échoue au-delà de 40 lignes (erreur serveur) | Bloque les commandes des centrales d'achat |
| R-04 | Absence de reprise de l'historique des tarifs négociés par client | Impossible de facturer aux conditions contractuelles en vigueur |

### 3.2 Réserves non bloquantes

| N° | Description |
|---|---|
| R-05 | Libellés de colonnes tronqués dans l'export tableur |
| R-06 | Tri par défaut de la liste des commandes non conforme à la demande |
| R-07 | Absence de raccourci clavier sur l'écran de saisie rapide |
| R-08 | Format de date incohérent entre deux écrans (JJ/MM/AAAA et AAAA-MM-JJ) |
| R-09 | Logo NOVERIA non intégré aux modèles d'impression |
| R-10 | Message d'erreur non traduit en français sur l'écran de rapprochement |
| R-11 | Pagination limitée à 50 lignes, non paramétrable |
| R-12 | Absence de journalisation des modifications de fiche article |

## 4. Conséquences

En application de l'article 9 du contrat, la présence d'au moins une réserve bloquante **suspend la recette du lot 2**. Celle-ci ne sera réputée acquise qu'après levée de l'intégralité des réserves R-01 à R-04.

Le Prestataire dispose de **quinze (15) jours ouvrés** à compter de ce jour pour procéder à cette levée, soit **au plus tard le 12 novembre 2024**.

Le Client rappelle que la date de livraison contractuelle du lot 2 était fixée au 18 octobre 2024 et qu'il se réserve expressément le bénéfice de l'article 8 du contrat.

Le Prestataire indique pour sa part que les réserves R-01 et R-04 résultent selon lui d'évolutions du besoin exprimées postérieurement au cahier des charges. Le Client conteste cette analyse.

---

Fait à Lyon, le 18 octobre 2024, en deux exemplaires.

|  |  |
|---|---|
| **Pour NOVERIA DISTRIBUTION** | **Pour ALTIMEO CONSEIL** |
| Julien BRESSAND | Karim BENALI |
| *(signature)* | *(signature)* |
