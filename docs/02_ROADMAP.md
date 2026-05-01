# Roadmap de refactor — Module `recouvrement_contentieux`

## Phase 0 — Préparation (1/2 j)

- Bumper version manifest `19.0.1.0.3` → `19.0.2.0.0` (rupture majeure)
- Créer dossier `migrations/19.0.2.0.0/` avec script `pre-migrate.py` + `post-migrate.py`
- Geler la branche actuelle dans un tag git `v1-legacy`

---

## Phase 1 — Fondation backend (8 j) ⭐ ON FAIT ÇA EN PREMIER

### 1.1 — Modèle `recouvrement.facture`
- Ajout : `mois_upload` (Char ou Selection), `statut_interface` (Selection), `montant_paye` (Monetary computed), `reste_a_payer` (Monetary computed), `lettrage_ids` (One2many)
- Renommer state `recouvrement_status` valeur `bloque` → `bloque_juridique` pour distinguer du blocage technique
- Ajout valeur `bloque_technique` à `recouvrement_status`
- Verrou juridique : `write()` rejette si `recouvrement_status in (precontentieux, contentieux, bloque_juridique)` SAUF si contexte d'import autorisé + statut cible reste valide
- Suppression `chez_laila`/`chez_bennis` (ou renommage)

### 1.2 — Modèle `recouvrement.recouvrement` (Dossier)
- `facture_id` (Many2one) → `facture_ids` (One2many) — **rupture majeure**
- Ajout `nombre_factures` (Integer computed)
- Recalcul `montant_ttc`, `montant_encaisse`, `reste_a_recouvrer` comme **somme** sur factures
- Logique de regroupement à l'import : factures avec même `client.client_type_id.procedure_id` + même `date_depot_client` → même dossier
- État renommés : `ouvert` / `solde` / `bloque` (pour rester proche du cahier)
- `_compute_next_action_date` : prend en compte la date de réalisation prévue de la phase courante (chronomètre strict)

### 1.3 — NOUVEAU modèle `recouvrement.lettrage`
- Champs : `encaissement_id`, `facture_id`, `montant_affecte`, `facture_montant_ttc` (snapshot), `facture_reste_a_payer` (snapshot), `currency_id`, `date_lettrage`
- Contrainte SQL : `montant_affecte > 0`
- Contrainte Python : `montant_affecte ≤ encaissement.reste_a_allouer` ET `≤ facture.reste_a_payer` au moment du lettrage
- À la création : déclenche recompute des `montant_paye` / `montant_alloue` / `reste_*`
- À la suppression : libère le montant côté encaissement et facture

### 1.4 — Modèle `recouvrement.encaissement` refactor
- Suppression `facture_id` (lien direct)
- Suppression `recouvrement_id` (lien direct)
- `client_id` devient Many2one **direct** (plus de related)
- Ajout : `montant_alloue` (computed sum lettrages), `reste_a_allouer` (computed), `etat_lettrage` Selection (`en_cours` / `solde`)
- Ajout `lettrage_ids` (One2many)

### 1.5 — Modèle `recouvrement.action.template`
- Ajout `statut_interface_cible` Selection (`vert`, `orange`, `rouge`, `mauve`)
- Action_type : réduit à `appel`, `email`, `courrier`, `mise_en_demeure`, `contentieux` (5 canoniques)
- Suppression valeurs `relance_1`, `relance_2`, `suivi` (le nom + séquence suffisent)

### 1.6 — Modèle `recouvrement.procedure`
- Suppression champs `delay_appel`, `delay_relance_1`, `delay_relance_2`, `delay_contentieux` (redondants avec `action_template_ids.delay`)

### 1.7 — Fusion `recouvrement.appel` + `recouvrement.email` → `recouvrement.action`
- Modèle unifié avec attributs spécifiques visibles selon `action_type`
- Ajout `client_id` (Many2one) — cible précise dans le dossier
- Ajout `action_template_id` (Many2one)
- Ajout state `reporte` + méthode `action_reporter()` qui :
  1. passe l'action courante à `reporte`
  2. crée une nouvelle action en `todo` à J+1 avec note auto « Reporté depuis l'action #X »
- Champs spécifiques email : `destinataire_email`, `corps_email`, `pieces_jointes_ids`, `modele_utilise`
- Champs spécifiques appel : `duree_minutes`, `notes_appel`, `action_prise`
- Logique Outlook centralisée (un seul code à maintenir au lieu de 2 copies)
- Logique d'envoi mail centralisée

### 1.8 — Modèle `recouvrement.client.type`
- RAS, modèle déjà conforme

### 1.9 — Sécurité
- Ajout access control pour `recouvrement.lettrage` (user lecture, manager full)
- Suppression access pour `recouvrement.appel` et `recouvrement.email` (modèles fusionnés)

### 1.10 — Migration
- Script `post-migrate.py` :
  1. Pour chaque dossier existant (1:1 facture), créer un nouveau dossier multi-facture en regroupant par `client_type_id.procedure_id` + `date_depot_client`
  2. Pour chaque encaissement existant lié à une facture : créer un `recouvrement.lettrage` avec `montant_affecte = encaissement.montant`, puis vider `encaissement.facture_id`
  3. Pour chaque `recouvrement.appel` et `recouvrement.email` : créer une ligne `recouvrement.action` correspondante, copier les champs spécifiques
  4. Initialiser `statut_interface = vert` et `mois_upload = 'Pré-migration'` sur factures existantes

---

## Phase 2 — Vues métier alignées (3 j)

### 2.1 — Menu réorganisé selon ta spec
```
Recouvrement
├── Vue d'ensemble
│   └── Tableau de bord (OWL)
├── Facturation
│   ├── Toutes les factures (list moderne)
│   └── Importer des factures (page OWL custom, plus wizard)
├── Encaissement
│   ├── Encaissements (list + détail avec lettrage dynamique)
│   └── Importer des encaissements (page OWL custom)
├── Suivi de recouvrement
│   └── Dossiers de recouvrements (list groupée par phase)
├── Relances
│   ├── Calendrier (calendar view)
│   ├── Appels (list filtrée hors-procédure)
│   └── Emails (list filtrée hors-procédure)
└── Paramétrage
    ├── Modèles d'actions
    ├── Procédures de recouvrement
    ├── Types de clients
    └── Clients
```

### 2.2 — Vues form refactorées
- Form facture : ajout panneau lettrages (One2many readonly)
- Form encaissement : ajout panneau **lettrage interactif** (sera remplacé par OWL phase 3)
- Form dossier : panneau factures groupées par client + stepper de phases
- Form action unifiée : champs conditionnels par `action_type`

### 2.3 — Search views enrichis
- Filtres latéraux par `statut_interface` (couleurs)
- Filtres par `mois_upload`
- Group by stratégie / phase courante

---

## Phase 3 — UI OWL moderne style SaaS (10 j) — palette CID

### 3.1 — Système de design CID
Couleurs extraites du logo :
- **Bleu CID** `#1E4D8C` (principal)
- **Bleu clair** `#3B82E0`
- **Orange CID** `#F39200` (accent/CTA)
- **Orange clair** `#FFB347`

Définition d'un fichier `_design_tokens.scss` avec :
- Couleurs sémantiques (`--cid-primary`, `--cid-accent`, `--cid-success`, `--cid-warning`, `--cid-danger`, `--cid-purple` pour mauve)
- Spacing system (4px base)
- Typo (Inter, sizes 12/14/16/18/24/32)
- Shadows (sm/md/lg/xl)
- Radius (4/8/12/16)

### 3.2 — Bibliothèque de composants OWL custom

```
static/src/components/
├── ui/
│   ├── button/         (variants: primary, secondary, ghost, danger)
│   ├── badge/          (variants: status colors, sizes)
│   ├── card/           
│   ├── dialog/         (modal accessible)
│   ├── toast/          (système de notifications globales)
│   ├── dropzone/       (file upload moderne avec preview)
│   ├── stepper/        (enchaînement phases)
│   ├── pagination/     
│   ├── data_table/     (table avec tri, sticky header)
│   ├── filter_sidebar/ (filtres latéraux)
│   ├── status_pill/    (vert/orange/rouge/mauve)
│   ├── empty_state/    
│   ├── skeleton/       (loaders)
│   └── tooltip/
└── chatbot/            (popup flottant + input NLQ)
```

### 3.3 — Pages OWL dédiées
- `recouvrement.import_factures` (client action, pas wizard)
- `recouvrement.import_encaissements` (idem)
- `recouvrement.encaissement_detail` (sélection client → factures non soldées → lettrage live avec compteur)
- `recouvrement.dossier_detail` (factures groupées + stepper phases)
- `recouvrement.action_execution` (page dédiée appel/email selon contexte)
- `recouvrement.dashboard` (refondu avec KPIs cahier)

### 3.4 — Chatbot flottant
- Bouton FAB en bas à droite, présent sur toutes les pages
- Click → panneau coulissant avec input + historique
- Backend : route HTTP qui prendra en charge la pile NLQ → LangChain → Odoo ORM (logique branchée plus tard)

---

## Phase 4 — Workflows métier avancés (3 j)

### 4.1 — Boucle de rattrapage J+1
- Dans `action.action_reporter()` : génération auto de l'action J+1
- Sur le dossier : ne pas avancer la phase tant que toutes les actions de la phase ne sont pas `done` ou ont leur boucle clôturée

### 4.2 — Blocage technique (orange)
- Hook après `action.action_done()` : si `action_template_id.statut_interface_cible == 'orange'` → propager `statut_interface=orange` sur les factures concernées + créer activité Odoo pour le pôle technique
- Vue dédiée « Factures en blocage technique » filtrée

### 4.3 — Lettrage dynamique
- Méthode RPC sur encaissement : `get_factures_disponibles(client_id)` → renvoie factures non soldées triées par date_facture
- Méthode RPC : `appliquer_lettrage(facture_id, montant)` avec validation contraintes (≤ reste à allouer, ≤ reste à payer)
- Méthode `auto_allouer()` : remplit séquentiellement par FIFO

### 4.4 — Propagation `statut_interface`
- Hook quand l'action courante change (sur le dossier) : copier le `statut_interface_cible` du template de la phase courante vers `facture.statut_interface`

---

## Phase 5 — Chatbot NLQ LangChain (5 j) — autonome

À traiter après que la fondation est solide. Stack proposée :
- Endpoint Odoo HTTP `/recouvrement/chat` (POST)
- LangChain agent avec outils :
  - `search_factures(criteria)` → ORM
  - `search_encaissements(criteria)`
  - `compute_kpi(name, period)`
  - `get_dossier_status(client_name)`
- LLM via API Anthropic Claude (clé en `res.config.settings`)
- Garde-fous : sandboxing ORM, `READ` only, limite de records

---

## Bilan global

| Phase | Effort | Statut après ce premier round |
|---|---|---|
| 0 — Préparation | 0,5 j | À faire |
| 1 — Fondation backend | 8 j | **Livré dans ce round (modèles + migration)** |
| 2 — Vues métier alignées | 3 j | À faire (round suivant) |
| 3 — UI OWL SaaS + palette CID | 10 j | À faire (rounds suivants par composants) |
| 4 — Workflows avancés | 3 j | À faire |
| 5 — Chatbot NLQ | 5 j | À faire (autonome, après le reste) |
| **Total** | **29,5 j** | |
