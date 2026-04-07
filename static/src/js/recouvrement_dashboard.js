/** @odoo-module **/

import { Component, onMounted, onPatched, onWillUnmount, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useBus, useService } from "@web/core/utils/hooks";

const SIDEBAR_SECTIONS = [
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
            { label: "Actions de recouvrement", icon: "fa-phone", actionXmlId: "recouvrement_contentieux.action_recouvrement_action" },
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

class RecouvrementDashboard extends Component {
    static template = "recouvrement_contentieux.RecouvrementDashboard";

    setup() {
        this.actionService = useService("action");
        this.sections = SIDEBAR_SECTIONS;
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
