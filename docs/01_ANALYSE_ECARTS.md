# Analyse d'écarts — Cahier de charge ↔ Code actuel

> Objectif : recenser **tous** les points où le code diverge du cahier, par ordre de criticité.
> Chaque écart est classé : 🔴 bloquant • 🟠 important • 🟡 cosmétique.

---

## 1. Modèle `recouvrement.recouvrement` (Dossier)

### 🔴 Écart structurel #1 — Cardinalité Dossier ↔ Facture

| Cahier de charge | Code actuel |
|---|---|
| `facture_ids` : **One2many** vers `recouvrement.facture` (un dossier = N factures) | `facture_id` : **Many2one** (un dossier = 1 facture) |
| « Un dossier regroupe les factures partageant la même Stratégie et la même Date de dépôt » | Chaque facture crée son propre dossier solitaire |
| « Le dossier ne se termine que si TOUTES les factures qu'il contient sont payées » | Pas de logique de clôture multi-facture |

**Impact** : c'est la **logique du convoi** décrite dans le cahier. Sans ça, impossible de :
- regrouper les factures par stratégie + date de dépôt à l'import
- afficher les factures groupées par client à l'intérieur d'un dossier
- gérer la phase suivante en attendant que **tous** les clients aient validé la phase actuelle

### 🔴 Écart #2 — Calcul de la phase suivante

| Cahier | Actuel |
|---|---|
| « Le délai de la phase suivante est calculé à partir de la date de réalisation prévue de la phase actuelle » | Délais calculés à partir de `date_depot_client` une fois pour toutes |

**Conséquence** : si la phase 1 (J+7) est reportée à J+10, la phase 2 (J+14) ne se décale pas → désynchro juridique.

### 🟠 Écart #3 — Champs manquants

| Champ cahier | Présent ? | Action |
|---|---|---|
| `nombre_factures` (calculé) | ❌ | À ajouter |
| `montant_ttc` (calculé sur factures) | ⚠️ Related sur 1 facture | À recalculer comme somme |
| `montant_encaisse` (via lettrages) | ⚠️ Sum des encaissements directs | À recalculer via lettrages |
| `reste_a_recouvrer` | ✅ | OK |
| `phase_courante` | ✅ | OK |
| `last_action_date` / `next_action_date` | ✅ | OK |
| State `solde` au lieu de `closed` | ⚠️ Naming | Aligner avec cahier |

---

## 2. Modèle `recouvrement.facture`

### 🔴 Écart #4 — Champs financiers calculés manquants

| Champ cahier | Présent ? |
|---|---|
| `montant_paye` (somme des lettrages) | ❌ |
| `reste_a_payer` (montant_ttc – montant_paye) | ❌ |
| `lettrage_ids` (One2many) | ❌ |

Sans ces champs, **le moteur de lettrage dynamique du chapitre 5 ne peut pas fonctionner** (« compteur Reste à allouer », « facture soldée si Reste à Payer = 0 »).

### 🔴 Écart #5 — Champ `mois_upload` manquant

> Cahier : « Marquage Analytique : Lors de l'import, l'utilisateur définit le Mois d'upload (ex : Avril 2026), permettant de figer les données pour les reportings et KPIs trimestriels. »

Le champ **`mois_upload`** n'existe pas. Il est demandé explicitement au chapitre 1.

### 🔴 Écart #6 — `statut_interface` (le pilotage visuel)

> Cahier : « Le statut choisi est automatiquement propagé à la facture via le champ `statut_interface`. »

Ce champ **manque totalement**. Or c'est le mécanisme central qui permet le « pilotage visuel direct des factures dans l'interface » avec les couleurs vert / orange / rouge / mauve.

### 🟠 Écart #7 — Logique d'upsert lors de l'import

Le cahier impose 3 règles strictes :

| Cas | Cahier | Wizard actuel |
|---|---|---|
| Cas 1 : `code_affaire` inexistant | CREATE avec statut `Normal` | À vérifier |
| Cas 2 : Existant + statut `Normal` | UPDATE | À vérifier |
| Cas 3 : Existant + statut `Pré-contentieux` / `Contentieux` / `Bloqué` | **REJETER** (verrou juridique) | Pas implémenté |

À auditer dans `wizard/import_facture_wizard.py` (388 lignes — vérifier la branche d'upsert).

### 🟡 Écart #8 — Champs « Chez Laila » / « Chez Bennis »

Présents dans le code, **absents du cahier**. Soit :
- ce sont des champs hérités d'un fichier Excel d'origine → renommer en `responsable_dossier_interne` / `responsable_validation` ;
- soit les supprimer si plus utilisés.

---

## 3. Modèle `recouvrement.encaissement` + Lettrage

### 🔴 Écart #9 — **Modèle `recouvrement.lettrage` ABSENT**

C'est le plus gros trou structurel après le dossier.

> Cahier : « Modèle : `recouvrement.lettrage` (Le pont de répartition) »
> - `encaissement_id` : Many2one
> - `facture_id` : Many2one
> - `montant_affecte` : Monetary
> - `facture_montant_ttc`, `facture_reste_a_payer` : snapshot au moment du lettrage

**Sans cette table** :
- Un encaissement de 5000 DH ne peut pas être réparti sur 3 factures
- Le « compteur Reste à allouer » du chapitre 5 est impossible
- La règle « jamais dépasser le montant » ne peut être enforced

### 🔴 Écart #10 — Encaissement lié à une facture au lieu d'un client

| Cahier | Actuel |
|---|---|
| `client_id` : Many2one **requis** (l'encaissement appartient au client) | `client_id` related sur `facture_id` |
| `facture_id` : ❌ pas de lien direct | `facture_id` Many2one direct |
| Lettrage via `lettrage_ids` | `recouvrement_id` direct (sera obsolète) |

> Cahier chap. 5 : « Un agent importe les Encaissements, clique sur une ligne et sélectionne le **Client** concerné. Le système affiche **uniquement les factures non soldées de ce client**. »

Le modèle actuel force le lien à une facture **avant** la sélection → casse le workflow.

### 🟠 Écart #11 — Champs manquants

| Champ cahier | Présent ? |
|---|---|
| `montant_alloue` (calculé via lettrages) | ❌ |
| `reste_a_allouer` (calculé) | ❌ |
| `etat_lettrage` (`en_cours` / `solde`) | ❌ |

---

## 4. Modèle `recouvrement.action.template`

### 🔴 Écart #12 — Champ `statut_interface_cible` ABSENT

> Cahier : « Une nouvelle colonne **statut** (vert, rouge, orange, mauve) est ajoutée aux phases. L'agent définit ce statut pour chaque phase de relance. »

C'est **le mécanisme central** du moteur de stratégie visuel. Sans ce champ, impossible de propager la couleur de la phase active à la facture.

### 🟠 Écart #13 — Liste des `action_type`

Le cahier liste : `appel`, `email`, `courrier`, `mise_en_demeure`, `contentieux`.
Le code a en plus : `relance_1`, `relance_2`, `suivi`.

Ces sous-types empiètent sur le rôle de la **séquence + nom**. Recommandation : 5 types canoniques + nom libre + séquence.

---

## 5. Modèle `recouvrement.action`

### 🔴 Écart #14 — État `reporte` manquant

> Cahier : « Si un client ne répond pas, l'action est marquée "Reportée". Une nouvelle action est générée à J+1 dans le même dossier. »

Le state actuel est `(todo, done, cancel)`. Il manque **`reporte`**, qui pilote la **boucle de rattrapage J+1**.

### 🔴 Écart #15 — `client_id` manquant sur l'action

Puisque le dossier est multi-clients (cf. écart #1), une action **doit** identifier précisément quel client elle cible.

> Cahier : « `client_id` : Many2one res.partner (Identifie le client cible de cette action précise dans le dossier) »

### 🔴 Écart #16 — Action « unifiée » fragmentée en 3 modèles

Le cahier prescrit **un seul** modèle `recouvrement.action` avec champs conditionnels :

```
Attributs Communs : name, comment, is_overdue
Attributs Spécifiques (Appel) : duree_minutes, notes_appel
Attributs Spécifiques (Email) : destinataire_email, corps_email
```

Le code actuel a :
- `recouvrement.action` (squelette générique)
- `recouvrement.appel` (modèle séparé, 246 lignes, avec sync Outlook)
- `recouvrement.email` (modèle séparé, 320 lignes, avec sync Outlook)

**Décision recommandée** : fusionner en un seul `recouvrement.action` avec champs conditionnels visibles selon `action_type`, et déplacer la logique Outlook + envoi mail dessus. Ça aligne le code avec le cahier ET élimine la duplication massive (sync Outlook copiée-collée).

### 🟠 Écart #17 — `action_template_id` manquant

> Cahier : « `action_template_id` : Many2one `recouvrement.action.template` »

Sans ce lien, impossible de tracer une action exécutée vers son modèle d'origine, ni de pré-remplir l'objet/corps email depuis le template.

---

## 6. Workflow « Blocage technique » (mention utilisateur)

> Demande : « si l'agent a choisi statut orange (blocage technique après une phase) cette facture est envoyée au pôle technique pour la résolution »

Ce workflow n'est **pas** dans le cahier mais est demandé. Il faut :
- Détecter `statut_interface = orange` après exécution d'une action
- Ajouter un champ `pole_technique_id` ou utiliser `pole_id` existant + un `state` `en_blocage_technique` sur la facture
- Notifier le pôle (mail.activity ou notification OWL)
- Bloquer la progression dans la stratégie tant que le blocage n'est pas levé

---

## 7. Sécurité & droits d'accès

### 🟡 Écart #18 — Pas d'access pour `recouvrement.lettrage`

Logique : ce modèle n'existe pas encore. À ajouter.

### 🟡 Écart #19 — Permissions strictes sur facture

Le cahier impose un verrou juridique. Les `write` sur facture en `pré-contentieux` / `contentieux` / `bloqué` doivent être **bloqués au niveau modèle** (pas seulement vue). Le code actuel a un `write()` qui lève `UserError` si `state != 'draft'` — c'est partiellement bon mais la condition est sur `state`, pas sur `recouvrement_status`. Le cahier dit explicitement « si le **statut** est Pré-contentieux/Contentieux/Bloqué », donc c'est `recouvrement_status` qu'il faut tester.

---

## 8. Frontend / OWL / UX (résumé — détail dans `02_ROADMAP.md`)

### 🔴 Bloquants UX

- **Pas de page d'exécution dédiée** pour clic facture → ouverture appel/email (« nouvelle page de saisie dédiée et spacieuse » ≠ pop-up)
- **Pas de palette CID** (bleu + orange du logo) appliquée comme système de design
- **Pas de composants OWL custom** (Toast, Dialog, Pagination, FileDropzone, Stepper, Badge)
- **Imports actuels = wizards Odoo** (cahier : remplacer par une page moderne avec dropzone)
- **Pas de chatbot flottant** sur toutes les pages
- **Liste des factures = vue list Odoo standard** sans pagination/filtres latéraux modernes

### 🟠 Cosmétique

- Statuts visuels (badges colorés vert/orange/rouge/mauve) pas en place
- Stepper d'enchaînement des phases dans le détail dossier absent
- Calendrier des actions présent mais pas stylé "SaaS"

---

## 9. Synthèse — top 5 chantiers à traiter dans l'ordre

| # | Chantier | Criticité | Effort estimé |
|---|---|---|---|
| 1 | Refactor `recouvrement.recouvrement` (dossier multi-factures) + regroupement à l'import | 🔴 | 2 j |
| 2 | Création `recouvrement.lettrage` + refactor `recouvrement.encaissement` (par client) | 🔴 | 2 j |
| 3 | Ajout `statut_interface` + `statut_interface_cible` + propagation auto | 🔴 | 1 j |
| 4 | Fusion `recouvrement.appel` + `recouvrement.email` → `recouvrement.action` unifié + état `reporte` + boucle J+1 | 🔴 | 2 j |
| 5 | Ajout `montant_paye` / `reste_a_payer` / `mois_upload` + verrou juridique sur upsert | 🟠 | 1 j |

**Total backend : ~8 jours.** Ensuite seulement on attaque l'UI OWL (palette CID, composants, dashboard, chatbot) — environ 10–12 jours.
