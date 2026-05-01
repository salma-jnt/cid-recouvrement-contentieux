# Recouvrement, litiges et contentieux — CID Développement

Module Odoo 19 de gestion du recouvrement, des litiges et du contentieux pour CID Développement, avec interface SaaS moderne (composants OWL custom + chatbot NLQ).

**Version :** `19.0.2.0.0` (refactor majeur depuis v1)

---

## Sommaire

1. [Architecture en bref](#architecture-en-bref)
2. [Installation](#installation)
3. [Migration depuis la v1](#migration-depuis-la-v1)
4. [Activation du chatbot LangChain (optionnel)](#activation-du-chatbot-langchain-optionnel)
5. [Structure du module](#structure-du-module)
6. [Référence des modèles](#référence-des-modèles)
7. [Référence des composants OWL](#référence-des-composants-owl)
8. [Workflows métier](#workflows-métier)

---

## Architecture en bref

### Backend (Odoo / Python)

- **9 modèles métier** dont `recouvrement.lettrage` (nouveau) et `recouvrement.action` unifié
- **Logique du convoi** : un dossier regroupe N factures partageant la même stratégie + date de dépôt
- **Lettrage dynamique** avec contraintes anti-dépassement
- **Verrou juridique** : factures en pré-contentieux/contentieux/bloqué non modifiables
- **Boucle de rattrapage J+1** sur action reportée
- **Pilotage visuel** par couleurs (vert/orange/rouge/mauve) propagées de la phase courante vers la facture
- **Workflow blocage technique** : statut orange → notification activité Odoo au pôle technique

### Frontend (OWL + SCSS)

- **Design system CID** : palette extraite du logo (bleu `#1E4D8C` + orange `#F39200`)
- **11 composants UI custom** réutilisables (Button, Badge, StatusPill, Card, Skeleton, EmptyState, Dialog, Toast, Dropzone, Stepper, Pagination, KpiCard)
- **5 pages OWL pleines** (Import Factures, Encaissement Live-Lettrage, Détail Dossier, Dashboard, Exécution d'Action)
- **Chatbot flottant** présent sur toutes les pages, avec fallback stub fonctionnel et activation LangChain optionnelle

### Endpoints HTTP

- `POST /recouvrement/chat` — chatbot NLQ (mode stub par défaut, agent LangChain si clé API)

---

## Installation

```bash
# Cloner ou copier le module dans addons/
cp -r recouvrement_contentieux /path/to/odoo/addons/

# Installer les dépendances Python obligatoires
pip install openpyxl

# Redémarrer Odoo et installer le module via l'UI ou :
./odoo-bin -c odoo.conf -u recouvrement_contentieux -d <db_name>
```

### Dépendances Python

| Paquet | Obligatoire | Usage |
|---|---|---|
| `openpyxl` | ✅ | Import des fichiers Excel |
| `langchain` | optionnel | Chatbot NLQ mode agent |
| `langchain-anthropic` | optionnel | Chatbot NLQ mode agent |

---

## Migration depuis la v1

Le module détecte la version installée et exécute automatiquement les scripts dans `migrations/19.0.2.0.0/` :

1. **`pre-migrate.py`** ajoute les nouvelles colonnes (`mois_upload`, `statut_interface`, `montant_paye`, `reste_a_payer`, `date_depot_groupe`, `nombre_factures`, `montant_alloue`, `reste_a_allouer`, `etat_lettrage`, `statut_interface_cible`, `client_id` sur action, etc.) et mappe les anciens codes d'état.

2. **`post-migrate.py`** :
   - Initialise `mois_upload` et `statut_interface=vert` sur les factures existantes
   - Regroupe les anciens dossiers 1:1 en convois multi-factures (procédure × date de dépôt)
   - Convertit chaque encaissement v1 (lié à une facture) en encaissement v2 + lettrage du montant complet
   - Migre `recouvrement.appel` et `recouvrement.email` vers le modèle unifié `recouvrement.action`

> **⚠ Avant migration** : faire un backup de la base. Le passage 1:1 → 1:N est une rupture irréversible.

---

## Activation du chatbot LangChain (optionnel)

Le chatbot fonctionne en deux modes :

| Mode | Activation | Capacités |
|---|---|---|
| **Stub** (défaut) | Aucune action | Réponses keyword-based : factures non soldées, total encaissé, top clients, actions du jour |
| **Agent** | Clé API + dépendances | Langage naturel complet via Claude Sonnet 4.5, avec 5 outils ORM sandboxés |

Pour activer le mode agent :

```bash
# Sur le serveur Odoo
pip install langchain langchain-anthropic
```

Puis dans Odoo : **Configuration → Recouvrement → Clé API Anthropic** → coller la clé.

Outils LangChain exposés :

- `count_factures_non_soldees(client_name?)`
- `total_encaisse(period: today|week|month|year|all)`
- `top_clients_a_recouvrer(limit)`
- `get_dossier_status(client_name)`
- `repartition_par_couleur()`

Tous READ-ONLY, limite de 100–10000 records selon l'outil.

---

## Structure du module

```
recouvrement_contentieux/
├── __manifest__.py                       Module v2.0.0
├── __init__.py
│
├── controllers/
│   └── chatbot_controller.py             /recouvrement/chat (LangChain prêt)
│
├── data/
│   ├── recouvrement_data.xml             Procédures + types client + 7 templates standards
│   └── recouvrement_sequences.xml
│
├── docs/
│   ├── 01_ANALYSE_ECARTS.md              Analyse cahier ↔ code
│   └── 02_ROADMAP.md                     Plan en 5 phases
│
├── migrations/19.0.2.0.0/
│   ├── pre-migrate.py                    Ajout des colonnes
│   └── post-migrate.py                   Conversion des données v1 → v2
│
├── models/                               9 modèles métier
│   ├── recouvrement_facture.py
│   ├── recouvrement_recouvrement.py     (Dossier multi-factures)
│   ├── recouvrement_lettrage.py         (NOUVEAU)
│   ├── recouvrement_encaissement.py
│   ├── recouvrement_action.py           (unifié appel/email/courrier/MED)
│   ├── recouvrement_procedure.py
│   ├── recouvrement_client_type.py
│   ├── res_partner.py
│   ├── res_config_settings.py           (clé API Anthropic ici)
│   └── outlook_graph_service.py
│
├── security/
│   ├── ir.model.access.csv               (lettrage ajouté, appel/email retirés)
│   └── recouvrement_security.xml
│
├── static/src/
│   ├── scss/
│   │   ├── _design_tokens.scss           Palette CID complète
│   │   ├── _mixins.scss
│   │   └── recouvrement.scss             Master entry
│   ├── services/
│   │   └── toast_service.js              useService("cid_toast")
│   └── components/
│       ├── ui/                           11 composants OWL custom
│       │   ├── button/, badge/, status_pill/, card/,
│       │   ├── skeleton/, empty_state/, dialog/, toast/,
│       │   └── dropzone/, stepper/, pagination/, kpi_card/
│       ├── chatbot/                      FAB + panneau coulissant
│       └── pages/                        5 pages OWL pleines
│           ├── import_factures/
│           ├── encaissement_lettrage/    (compteur live)
│           ├── dossier_detail/           (stepper + groupé client)
│           ├── dashboard/                (KPIs cahier)
│           └── action_execution/         (appel ou email contextuel)
│
├── views/                                10 fichiers de vues XML
│   ├── recouvrement_menu.xml             Menu hiérarchique cahier
│   ├── recouvrement_facture_views.xml
│   ├── recouvrement_dossier_views.xml
│   ├── recouvrement_encaissement_views.xml
│   ├── recouvrement_action_views.xml     (form unifiée avec onglets conditionnels)
│   ├── recouvrement_procedure_views.xml  (statut_interface_cible visible)
│   ├── recouvrement_client_type_views.xml
│   ├── recouvrement_lettrage_views.xml
│   ├── res_partner_views.xml
│   └── res_config_settings_views.xml
│
└── wizard/
    ├── import_facture_wizard.py          (3 cas d'upsert du cahier)
    └── import_encaissement_wizard.py
```

---

## Référence des modèles

### `recouvrement.facture`

Champs clés : `name`, `code_affaire`, `client_id`, `recouvrement_status`, `statut_interface`, `mois_upload`, `montant_ttc`, `montant_paye` (computed), `reste_a_payer` (computed), `lettrage_ids`, `recouvrement_id`.

Verrou juridique enforcé dans `write()`. Méthodes publiques : `propagate_statut_interface(color)`, `mark_recouvre()`, `_notifier_pole_technique(action)`.

### `recouvrement.recouvrement` (Dossier)

Champs clés : `procedure_id`, `date_depot_groupe`, `facture_ids` (One2many), `nombre_factures`, `nombre_clients`, `montant_ttc/encaisse/reste_a_recouvrer` (sommes), `phase_courante`, `prochaine_echeance`, `state` (ouvert/en_cours/en_retard/bloque/solde).

Méthodes : `get_or_create_for_facture(facture)`, `action_generate_actions()` (génère N actions par client × phase), `_update_state()`.

### `recouvrement.lettrage`

Pont encaissement ↔ facture. Champs : `encaissement_id`, `facture_id`, `montant_affecte`, snapshots audit. Contraintes Python anti-dépassement (reste à allouer / reste à payer / cohérence client).

### `recouvrement.encaissement`

Client-centric (plus de lien direct facture). Champs : `client_id`, `montant`, `montant_alloue` (computed), `reste_a_allouer` (computed), `etat_lettrage`. RPC : `get_factures_disponibles()`, `appliquer_lettrage(facture_id, montant)`, `auto_allouer_fifo()`, `action_open_lettrage_page()`.

### `recouvrement.action`

Modèle unifié remplaçant `recouvrement.appel` + `recouvrement.email`. États : `todo` / `done` / `reporte` / `cancel`. Méthode `action_reporter()` génère automatiquement une action J+1.

### `recouvrement.action.template`

Template d'action / phase. Champ critique : `statut_interface_cible` (vert/orange/rouge/mauve) propagé automatiquement à `facture.statut_interface` quand la phase devient courante.

---

## Référence des composants OWL

Tous les composants utilisent les CSS variables de `_design_tokens.scss`. Voir `static/src/components/ui/<nom>/` pour le code.

| Composant | Slots / Props |
|---|---|
| `<CidButton variant size icon loading onClick>` | `variant`: primary, accent, secondary, ghost, danger, success |
| `<CidBadge variant subtle size icon>` | 8 couleurs × 2 styles (solid / subtle) |
| `<CidStatusPill color withDot>` | 4 couleurs cahier (vert/orange/rouge/mauve) |
| `<CidCard padded elevated interactive accentBar>` | Slots `header` / `default` / `footer` |
| `<CidSkeleton width height rounded lines circle>` | Loader animé shimmer |
| `<CidEmptyState icon title description actionLabel onAction>` | État vide avec CTA |
| `<CidDialog open title size onClose>` | Modal accessible (Esc, overlay) |
| `<CidToastContainer>` | Service global `useService("cid_toast")` |
| `<CidDropzone accept multiple maxSizeMB files onFilesChanged>` | Drag & drop + preview |
| `<CidStepper steps currentIndex orientation>` | Phases avec couleurs cahier |
| `<CidPagination total page pageSize onPageChange>` | Avec ellipsis intelligent |
| `<CidKpiCard label value icon trend accent>` | Cards dashboard avec accent bar |

---

## Workflows métier

### Import factures

1. Import via page OWL `import_factures_page` ou wizard XML
2. Pour chaque ligne :
   - **Cas 1** (code_affaire inexistant) → CREATE statut Normal + statut_interface vert
   - **Cas 2** (existante + Normal) → UPDATE
   - **Cas 3** (existante + précont/cont/bloqué) → REJET (loggé dans `errors`, compté dans `locked_count`)
3. Pour chaque nouvelle facture : appel à `recouvrement.recouvrement.get_or_create_for_facture()` → rattachement à un dossier groupant par procédure × date de dépôt
4. Génération automatique des actions du dossier (N templates × M clients)

### Lettrage encaissement (chap. 5 cahier)

1. Page OWL `encaissement_lettrage_page` chargée avec `encaissement_id` en context
2. RPC `get_factures_disponibles()` charge uniquement les factures non soldées du client
3. Compteur **« Reste à allouer » live** : décroît en temps réel à chaque saisie d'input
4. Validation côté UI : jamais dépasser `reste_a_allouer` ni `facture.reste_a_payer`
5. Au save : RPC `appliquer_lettrage(facture_id, montant)` × N → contrainte serveur revérifiée
6. Si `reste_a_payer` d'une facture tombe à 0 → propagation `recouvrement_status = recouvre`
7. Si toutes les factures du dossier sont à 0 → `dossier.state = solde`

### Boucle de rattrapage J+1 (cahier)

Quand l'agent qualifie un appel comme « non joignable » (page d'exécution d'action) :

1. Action courante : `state = reporte`
2. Création automatique d'une nouvelle action en `todo` à `mandatory_date + 1 jour`
3. Note auto : « Reporté depuis l'action #X »
4. Le dossier reste sur la même phase tant qu'au moins une action n'est pas done

### Blocage technique (extension cahier)

Quand une phase a `statut_interface_cible = orange` et passe au statut courant :

1. Toutes les factures du client concerné dans le dossier passent à `statut_interface = orange`
2. `recouvrement_status` passe à `bloque_technique`
3. Création d'une activité Odoo (`mail.activity_data_todo`) sur les factures, assignée au pôle technique
4. Visible via le menu **Suivi de recouvrement → Blocages techniques**
5. La progression de la stratégie est suspendue jusqu'à résolution

---

## Crédits

CID Développement — refactor v2.0.0
