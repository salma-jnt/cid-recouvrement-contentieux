/** @odoo-module **/

import { Component, onMounted, onPatched, onWillStart, onWillUnmount, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useBus, useService } from "@web/core/utils/hooks";

const SIDEBAR_SECTIONS = [
    {
        title: "Vue d'ensemble",
        items: [
            { label: "Tableau de bord", icon: "fa-home", actionXmlId: "recouvrement_contentieux.action_recouvrement_dashboard" },
        ],
    },
    {
        title: "Facturation",
        items: [
            { label: "Toutes les factures", icon: "fa-file-text-o", actionXmlId: "recouvrement_contentieux.action_recouvrement_facture" },
            { label: "Factures standard", icon: "fa-files-o", actionXmlId: "recouvrement_contentieux.action_recouvrement_facture_standard" },
            { label: "Factures groupement", icon: "fa-clone", actionXmlId: "recouvrement_contentieux.action_recouvrement_facture_groupement" },
            { label: "Factures proforma", icon: "fa-sticky-note-o", actionXmlId: "recouvrement_contentieux.action_recouvrement_facture_proforma" },
            { label: "Factures d'avance", icon: "fa-money", actionXmlId: "recouvrement_contentieux.action_recouvrement_facture_avance" },
            { label: "Importer des factures", icon: "fa-upload", actionXmlId: "recouvrement_contentieux.action_recouvrement_import_factures" },
        ],
    },
    {
        title: "Suivi de recouvrement",
        items: [
            { label: "Dossiers de recouvrement", icon: "fa-folder-open-o", actionXmlId: "recouvrement_contentieux.action_recouvrement_recouvrement" },
            { label: "Encaissements", icon: "fa-credit-card", actionXmlId: "recouvrement_contentieux.action_recouvrement_encaissement" },
        ],
    },
    {
        title: "Paramétrage",
        items: [
            { label: "Procédures de recouvrement", icon: "fa-sitemap", actionXmlId: "recouvrement_contentieux.action_recouvrement_procedure" },
            { label: "Modèles d'actions", icon: "fa-tasks", actionXmlId: "recouvrement_contentieux.action_recouvrement_action_template" },
            { label: "Types de clients", icon: "fa-users", actionXmlId: "recouvrement_contentieux.action_recouvrement_client_type" },
        ],
    },
];

function formatAmount(value) {
    return new Intl.NumberFormat("fr-FR", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
    }).format(Number(value || 0));
}

function formatDate(value) {
    if (!value) {
        return "-";
    }
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
        return value;
    }
    return new Intl.DateTimeFormat("fr-FR").format(date);
}

class RecouvrementDashboard extends Component {
    static template = "recouvrement_contentieux.RecouvrementDashboard";

    setup() {
        this.actionService = useService("action");
        this.orm = useService("orm");
        this.sections = SIDEBAR_SECTIONS;
        this.state = useState({
            loading: true,
            kpis: [],
            statusBreakdown: [],
            recentFactures: [],
            lateRecouvrements: [],
            recentEncaissements: [],
        });

        onWillStart(async () => {
            await this.loadDashboard();
        });
    }

    async loadDashboard() {
        this.state.loading = true;
        const [
            totalFactures,
            draftDossiers,
            openDossiers,
            lateDossiers,
            blockedDossiers,
            closedDossiers,
            facturesForTotal,
            encaissementsForTotal,
            recentFactures,
            lateRecouvrements,
            recentEncaissements,
        ] = await Promise.all([
            this.orm.searchCount("recouvrement.facture", []),
            this.orm.searchCount("recouvrement.recouvrement", [["state", "=", "draft"]]),
            this.orm.searchCount("recouvrement.recouvrement", [["state", "=", "open"]]),
            this.orm.searchCount("recouvrement.recouvrement", [["state", "=", "late"]]),
            this.orm.searchCount("recouvrement.recouvrement", [["state", "=", "blocked"]]),
            this.orm.searchCount("recouvrement.recouvrement", [["state", "=", "closed"]]),
            this.orm.searchRead("recouvrement.facture", [], ["montant_ttc"]),
            this.orm.searchRead("recouvrement.encaissement", [], ["montant"]),
            this.orm.searchRead(
                "recouvrement.facture",
                [],
                ["name", "client_id", "montant_ttc", "date_facture", "depot_display"],
                { limit: 5, order: "date_facture desc, id desc" }
            ),
            this.orm.searchRead(
                "recouvrement.recouvrement",
                [["state", "in", ["late", "blocked"]]],
                ["facture_id", "client_id", "prochaine_echeance", "reste_a_recouvrer"],
                { limit: 5, order: "prochaine_echeance asc, id desc" }
            ),
            this.orm.searchRead(
                "recouvrement.encaissement",
                [],
                ["name", "facture_id", "montant", "date_operation"],
                { limit: 5, order: "date_operation desc, id desc" }
            ),
        ]);

        const montantTotalFactures = facturesForTotal.reduce((sum, item) => sum + (item.montant_ttc || 0), 0);
        const montantTotalEncaisse = encaissementsForTotal.reduce((sum, item) => sum + (item.montant || 0), 0);

        this.state.kpis = [
            {
                label: "Factures",
                value: String(totalFactures),
                icon: "fa-file-text-o",
                actionXmlId: "recouvrement_contentieux.action_recouvrement_facture",
            },
            {
                label: "Montant total TTC",
                value: `${formatAmount(montantTotalFactures)} MAD`,
                icon: "fa-money",
                actionXmlId: "recouvrement_contentieux.action_recouvrement_facture",
            },
            {
                label: "Dossiers ouverts",
                value: String(openDossiers),
                icon: "fa-folder-open-o",
                actionXmlId: "recouvrement_contentieux.action_recouvrement_recouvrement",
            },
            {
                label: "Dossiers en retard",
                value: String(lateDossiers + blockedDossiers),
                icon: "fa-exclamation-triangle",
                actionXmlId: "recouvrement_contentieux.action_recouvrement_recouvrement",
            },
            {
                label: "Montant encaissé",
                value: `${formatAmount(montantTotalEncaisse)} MAD`,
                icon: "fa-credit-card",
                actionXmlId: "recouvrement_contentieux.action_recouvrement_encaissement",
            },
        ];

        this.state.statusBreakdown = [
            { label: "Normal", value: String(draftDossiers), tone: "draft" },
            { label: "Précontentieux", value: String(openDossiers), tone: "open" },
            { label: "Contentieux", value: String(lateDossiers), tone: "late" },
            { label: "Bloqué", value: String(blockedDossiers), tone: "blocked" },
            { label: "Recouvré", value: String(closedDossiers), tone: "closed" },
        ];

        this.state.recentFactures = recentFactures.map((item) => ({
            id: item.id,
            name: item.name,
            client: item.client_id?.[1] || "-",
            date: formatDate(item.date_facture),
            depot: item.depot_display || "-",
            montant: `${formatAmount(item.montant_ttc)} MAD`,
        }));

        this.state.lateRecouvrements = lateRecouvrements.map((item) => ({
            id: item.id,
            name: item.facture_id?.[1] || "-",
            client: item.client_id?.[1] || "-",
            nextAction: formatDate(item.prochaine_echeance),
            montant: `${formatAmount(item.reste_a_recouvrer)} MAD`,
        }));

        this.state.recentEncaissements = recentEncaissements.map((item) => ({
            id: item.id,
            name: item.name,
            facture: item.facture_id?.[1] || "-",
            date: formatDate(item.date_operation),
            montant: `${formatAmount(item.montant)} MAD`,
        }));

        this.state.loading = false;
    }

    openAction(actionXmlId) {
        this.actionService.doAction(actionXmlId);
    }
}

class RecouvrementSidebar extends Component {
    static template = "recouvrement_contentieux.RecouvrementSidebar";

    setup() {
        this.actionService = useService("action");
        this.menuService = useService("menu");
        this.state = useState({ refresh: 0 });
        this.sections = SIDEBAR_SECTIONS;

        useBus(this.env.bus, "MENUS:APP-CHANGED", () => {
            this.state.refresh++;
            this._syncBodyClass();
        });

        onMounted(() => this._syncBodyClass());
        onPatched(() => this._syncBodyClass());
        onWillUnmount(() => document.body.classList.remove("o_recouvrement_sidebar_active"));
    }

    get isVisible() {
        const app = this.menuService.getCurrentApp();
        return app && app.name === "Recouvrement";
    }

    openAction(actionXmlId) {
        this.actionService.doAction(actionXmlId);
    }

    _syncBodyClass() {
        document.body.classList.toggle("o_recouvrement_sidebar_active", this.isVisible);
    }
}

registry.category("actions").add("recouvrement_contentieux.dashboard", RecouvrementDashboard);
registry.category("main_components").add("recouvrement_contentieux.sidebar", {
    Component: RecouvrementSidebar,
});
