/** @odoo-module **/

import { Component, onMounted, onPatched, onWillStart, onWillUnmount, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useBus, useService } from "@web/core/utils/hooks";

const SIDEBAR_SECTIONS = [
    // ── Section 1 : Vue d'ensemble ──────────────────────────────────────────
    {
        title: "Vue d'ensemble",
        items: [
            { label: "Tableau de bord", icon: "fa-home",
              actionXmlId: "recouvrement_contentieux.action_recouvrement_dashboard" },
        ],
    },

    // ── Section 2 : Facturation ──────────────────────────────────────────────
    // Ordre menu XML : Importer (seq 10) → Toutes les factures (seq 20)
    {
        title: "Facturation",
        items: [
            { label: "Importer des factures", icon: "fa-upload",
              actionXmlId: "recouvrement_contentieux.action_recouvrement_import_factures_modern" },
            { label: "Toutes les factures",   icon: "fa-file-text-o",
              actionXmlId: "recouvrement_contentieux.action_recouvrement_facture" },
        ],
    },

    // ── Section 3 : Encaissement ─────────────────────────────────────────────
    // Ordre menu XML : Importer (seq 10) → Encaissements (seq 20)
    {
        title: "Encaissement",
        items: [
            { label: "Importer des encaissements", icon: "fa-upload",
              actionXmlId: "recouvrement_contentieux.action_recouvrement_import_encaissements_modern" },
            { label: "Encaissements",              icon: "fa-credit-card",
              actionXmlId: "recouvrement_contentieux.action_recouvrement_encaissement" },
        ],
    },

    // ── Section 4 : Suivi de recouvrement ────────────────────────────────────
    // Ordre menu XML : Dossiers (seq 10) → Blocages techniques (seq 20)
    {
        title: "Suivi de recouvrement",
        items: [
            { label: "Dossiers de recouvrements", icon: "fa-folder-open-o",
              actionXmlId: "recouvrement_contentieux.action_recouvrement_recouvrement" },
            { label: "Blocages techniques",       icon: "fa-ban",
              actionXmlId: "recouvrement_contentieux.action_recouvrement_factures_blocage_technique" },
        ],
    },

    // ── Section 5 : Relances ─────────────────────────────────────────────────
    // Ordre menu XML : Calendrier (seq 10) → Appels (seq 20) → Emails (seq 30)
    {
        title: "Relances",
        items: [
            { label: "Calendrier", icon: "fa-calendar",
              actionXmlId: "recouvrement_contentieux.action_recouvrement_action_calendar" },
            { label: "Appels",     icon: "fa-phone",
              actionXmlId: "recouvrement_contentieux.action_recouvrement_action_appels" },
            { label: "Emails",     icon: "fa-envelope-o",
              actionXmlId: "recouvrement_contentieux.action_recouvrement_action_emails" },
        ],
    },

    // ── Section 6 : Paramétrage ──────────────────────────────────────────────
    // Ordre menu XML : Modèles (seq 10) → Procédures (seq 20) → Types (seq 30) → Clients (seq 40)
    {
        title: "Paramétrage",
        items: [
            { label: "Modèles d'actions",          icon: "fa-tasks",
              actionXmlId: "recouvrement_contentieux.action_recouvrement_action_template" },
            { label: "Procédures de recouvrement", icon: "fa-sitemap",
              actionXmlId: "recouvrement_contentieux.action_recouvrement_procedure" },
            { label: "Types de clients",           icon: "fa-users",
              actionXmlId: "recouvrement_contentieux.action_recouvrement_client_type" },
            { label: "Clients",                    icon: "fa-address-book-o",
              actionXmlId: "recouvrement_contentieux.action_recouvrement_clients" },
        ],
    },
];

function formatAmount(value) {
    return new Intl.NumberFormat("fr-FR", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
    }).format(Number(value || 0));
}

function formatCompactAmount(value) {
    const amount = Number(value || 0);
    const absAmount = Math.abs(amount);
    if (absAmount >= 1_000_000_000) {
        return `${formatAmount(amount / 1_000_000_000)} Milliard`;
    }
    if (absAmount >= 1_000_000) {
        return `${formatAmount(amount / 1_000_000)} M`;
    }
    return formatAmount(amount);
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

function toISODate(date) {
    return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
}

function toISODatetime(date) {
    return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 19);
}


// RecouvrementDashboard supprimé — remplacé par CidDashboard dans dashboard.js

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

// NB: l'enregistrement "actions" du dashboard est fait dans dashboard.js (CidDashboard).
// Ce fichier gère uniquement la sidebar persistante.
registry.category("main_components").add("recouvrement_contentieux.sidebar", {
    Component: RecouvrementSidebar,
});