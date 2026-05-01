{
    'name': 'Recouvrement, litiges et contentieux',
    'version': '19.0.2.0.0',
    'summary': 'Gestion moderne du recouvrement, des litiges et du contentieux (CID)',
    'description': """
Module de gestion des recouvrements, litiges et contentieux pour CID Développement.

Refactor v2.0.0 :
  - Dossier multi-factures (logique du convoi)
  - Lettrage dynamique encaissements ↔ factures (compteur live "Reste à allouer")
  - Action unifiée (appel/email/courrier/MED/contentieux)
  - Boucle de rattrapage J+1 (action reportée)
  - Pilotage visuel par couleurs (vert/orange/rouge/mauve)
  - UI moderne OWL avec design system CID (palette bleu + orange du logo)
  - Bibliothèque de composants OWL custom (Toast, Dialog, Dropzone, Stepper, KPI...)
  - Dashboard refondu avec KPIs cahier de charge
  - Page d'import factures moderne avec dropzone
  - Page de lettrage live (compteur en temps réel)
  - Page de détail dossier avec stepper de phases
  - Chatbot flottant (NLQ — pile LangChain à brancher en Phase 5)
""",
    'category': 'Accounting',
    'sequence': 10,
    'author': 'CID Développement',
    'license': 'OPL-1',
    'depends': ['base', 'web', 'account', 'hr', 'mail'],
    'data': [
        'security/recouvrement_security.xml',
        'security/ir.model.access.csv',
        'data/recouvrement_sequences.xml',
        'data/recouvrement_data.xml',
        # Vues
        'views/res_partner_views.xml',
        'views/res_config_settings_views.xml',
        'views/recouvrement_facture_views.xml',
        'views/recouvrement_encaissement_views.xml',
        'views/recouvrement_lettrage_views.xml',
        'views/recouvrement_dossier_views.xml',
        'views/recouvrement_action_views.xml',
        'views/recouvrement_procedure_views.xml',
        'views/recouvrement_client_type_views.xml',
        'views/recouvrement_menu.xml',
    ],
    'assets': {
        'web.assets_backend': [
            # ==========  DESIGN SYSTEM CID (master scss — doit être en 1er)  ==========
            'recouvrement_contentieux/static/src/scss/recouvrement.scss',

            # ==========  SERVICES (avant les composants qui en dépendent)  ==========
            'recouvrement_contentieux/static/src/services/toast_service.js',

            # ==========  COMPOSANTS UI (ordre : atomes → molécules)  ==========
            'recouvrement_contentieux/static/src/components/ui/button/button.js',
            'recouvrement_contentieux/static/src/components/ui/button/button.xml',
            'recouvrement_contentieux/static/src/components/ui/badge/badge.js',
            'recouvrement_contentieux/static/src/components/ui/badge/badge.xml',
            'recouvrement_contentieux/static/src/components/ui/status_pill/status_pill.js',
            'recouvrement_contentieux/static/src/components/ui/status_pill/status_pill.xml',
            'recouvrement_contentieux/static/src/components/ui/card/card.js',
            'recouvrement_contentieux/static/src/components/ui/card/card.xml',
            'recouvrement_contentieux/static/src/components/ui/skeleton/skeleton.js',
            'recouvrement_contentieux/static/src/components/ui/skeleton/skeleton.xml',
            'recouvrement_contentieux/static/src/components/ui/empty_state/empty_state.js',
            'recouvrement_contentieux/static/src/components/ui/empty_state/empty_state.xml',
            'recouvrement_contentieux/static/src/components/ui/dialog/dialog.js',
            'recouvrement_contentieux/static/src/components/ui/dialog/dialog.xml',
            'recouvrement_contentieux/static/src/components/ui/toast/toast.js',
            'recouvrement_contentieux/static/src/components/ui/toast/toast.xml',
            'recouvrement_contentieux/static/src/components/ui/dropzone/dropzone.js',
            'recouvrement_contentieux/static/src/components/ui/dropzone/dropzone.xml',
            'recouvrement_contentieux/static/src/components/ui/stepper/stepper.js',
            'recouvrement_contentieux/static/src/components/ui/stepper/stepper.xml',
            'recouvrement_contentieux/static/src/components/ui/pagination/pagination.js',
            'recouvrement_contentieux/static/src/components/ui/pagination/pagination.xml',
            'recouvrement_contentieux/static/src/components/ui/kpi_card/kpi_card.js',
            'recouvrement_contentieux/static/src/components/ui/kpi_card/kpi_card.xml',

            # ==========  DASHBOARD + SIDEBAR OWL (menu fixe persistant)  ==========
            # Ces 3 fichiers sont OBLIGATOIRES pour que la sidebar navy s'affiche.
            # recouvrement_dashboard.scss : styles du sidebar et du dashboard legacy
            # recouvrement_dashboard.xml  : template RecouvrementSidebar + RecouvrementDashboard
            # recouvrement_dashboard.js   : composants OWL + registry main_components (sidebar)
            'recouvrement_contentieux/static/src/scss/recouvrement_dashboard.scss',
            'recouvrement_contentieux/static/src/xml/recouvrement_dashboard.xml',
            'recouvrement_contentieux/static/src/js/recouvrement_dashboard.js',

            # ==========  CHATBOT  ==========
            'recouvrement_contentieux/static/src/components/chatbot/chatbot_fab.js',
            'recouvrement_contentieux/static/src/components/chatbot/chatbot_fab.xml',

            # ==========  PAGES OWL (après tous les composants UI dont elles dépendent)  ==========
            'recouvrement_contentieux/static/src/components/pages/import_factures/import_factures_page.js',
            'recouvrement_contentieux/static/src/components/pages/import_factures/import_factures_page.xml',

            'recouvrement_contentieux/static/src/components/pages/import_encaissements/import_encaissements_page.js',
            'recouvrement_contentieux/static/src/components/pages/import_encaissements/import_encaissements_page.xml',

            'recouvrement_contentieux/static/src/components/pages/encaissement_lettrage/encaissement_lettrage_page.js',
            'recouvrement_contentieux/static/src/components/pages/encaissement_lettrage/encaissement_lettrage_page.xml',

            'recouvrement_contentieux/static/src/components/pages/dossier_detail/dossier_detail_page.js',
            'recouvrement_contentieux/static/src/components/pages/dossier_detail/dossier_detail_page.xml',

            'recouvrement_contentieux/static/src/components/pages/dashboard/dashboard.js',
            'recouvrement_contentieux/static/src/components/pages/dashboard/dashboard.xml',

            'recouvrement_contentieux/static/src/components/pages/action_execution/action_execution_page.js',
            'recouvrement_contentieux/static/src/components/pages/action_execution/action_execution_page.xml',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}