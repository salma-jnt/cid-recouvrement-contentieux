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
            { label: "Importer des factures", icon: "fa-upload", actionXmlId: "recouvrement_contentieux.action_recouvrement_import_factures" },
        ],
    },
    {
        title: "Suivi de recouvrement",
        items: [
            { label: "Dossiers de recouvrement", icon: "fa-folder-open-o", actionXmlId: "recouvrement_contentieux.action_recouvrement_recouvrement" },
        ],
    },
    {
        title: "Encaissement",
        items: [
            { label: "Encaissements", icon: "fa-credit-card", actionXmlId: "recouvrement_contentieux.action_recouvrement_encaissement" },
            { label: "Importer des encaissements", icon: "fa-upload", actionXmlId: "recouvrement_contentieux.action_recouvrement_import_encaissements" },
        ],
    },
    {
        title: "Relances",
        items: [
            { label: "Appels", icon: "fa-phone", actionXmlId: "recouvrement_contentieux.action_recouvrement_appel" },
            { label: "Emails", icon: "fa-envelope-o", actionXmlId: "recouvrement_contentieux.action_recouvrement_email" },
            { label: "Calendrier", icon: "fa-calendar", actionXmlId: "recouvrement_contentieux.action_recouvrement_appel_calendar" },
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
            totalStatus: 0,
            donutStyle: "",
            dateFrom: "",
            dateTo: "",
            selectedScope: "dossiers",
            selectedStatus: "all",
            selectedCommercial: "all",
            commercialOptions: [],
            todayAgenda: [],
            weekAgenda: [],
            dossierRows: [],
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
        const now = new Date();
        const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 0, 0, 0);
        const todayEnd = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 23, 59, 59);
        const weekEnd = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 6, 23, 59, 59);

        const [dateMinFacture, dateMaxFacture, actionResponsibles] = await Promise.all([
            this.orm.searchRead("recouvrement.facture", [["date_facture", "!=", false]], ["date_facture"], { limit: 1, order: "date_facture asc" }),
            this.orm.searchRead("recouvrement.facture", [["date_facture", "!=", false]], ["date_facture"], { limit: 1, order: "date_facture desc" }),
            this.orm.searchRead("recouvrement.action", [["responsible_id", "!=", false]], ["responsible_id"], { limit: 10000 }),
        ]);

        if (!this.state.dateFrom && dateMinFacture.length) {
            this.state.dateFrom = dateMinFacture[0].date_facture;
        }
        if (!this.state.dateTo && dateMaxFacture.length) {
            this.state.dateTo = dateMaxFacture[0].date_facture;
        }

        const commercialMap = new Map();
        for (const item of actionResponsibles) {
            if (item.responsible_id?.[0]) {
                commercialMap.set(item.responsible_id[0], item.responsible_id[1]);
            }
        }
        this.state.commercialOptions = [{ id: "all", name: "Tous" }, ...Array.from(commercialMap.entries()).map(([id, name]) => ({ id: String(id), name }))];

        const factureDomain = [];
        const dossierDomain = [];
        const appelDomain = [];
        const encaissementDomain = [];

        if (this.state.dateFrom) {
            factureDomain.push(["date_facture", ">=", this.state.dateFrom]);
            dossierDomain.push(["prochaine_echeance", ">=", this.state.dateFrom]);
            appelDomain.push(["date_appel", ">=", `${this.state.dateFrom} 00:00:00`]);
            encaissementDomain.push(["date_operation", ">=", this.state.dateFrom]);
        }
        if (this.state.dateTo) {
            factureDomain.push(["date_facture", "<=", this.state.dateTo]);
            dossierDomain.push(["prochaine_echeance", "<=", this.state.dateTo]);
            appelDomain.push(["date_appel", "<=", `${this.state.dateTo} 23:59:59`]);
            encaissementDomain.push(["date_operation", "<=", this.state.dateTo]);
        }

        const factureStatusMap = {
            normal: "normal",
            open: "precontentieux",
            late: "contentieux",
            blocked: "bloque",
            closed: "recouvre",
        };

        if (this.state.selectedStatus !== "all") {
            dossierDomain.push(["state", "=", this.state.selectedStatus]);
            factureDomain.push(["recouvrement_status", "=", factureStatusMap[this.state.selectedStatus] || "normal"]);
        }

        if (this.state.selectedCommercial !== "all") {
            const responsibleId = Number(this.state.selectedCommercial);
            appelDomain.push(["responsable_id", "=", responsibleId]);
            const linkedActions = await this.orm.searchRead("recouvrement.action", [["responsible_id", "=", responsibleId]], ["recouvrement_id"], { limit: 10000 });
            const recouvrementIds = [...new Set(linkedActions.map((a) => a.recouvrement_id?.[0]).filter(Boolean))];
            if (recouvrementIds.length) {
                dossierDomain.push(["id", "in", recouvrementIds]);
                factureDomain.push(["recouvrement_id", "in", recouvrementIds]);
                encaissementDomain.push(["recouvrement_id", "in", recouvrementIds]);
            } else {
                dossierDomain.push(["id", "=", 0]);
                factureDomain.push(["id", "=", 0]);
                encaissementDomain.push(["id", "=", 0]);
            }
        }

        const [
            totalFactures,
            factureNormal,
            facturePre,
            factureContentieux,
            factureBloque,
            factureRecouvre,
            totalDossiers,
            draftDossiers,
            openDossiers,
            lateDossiers,
            blockedDossiers,
            closedDossiers,
            recouvrementsOpen,
            encaissementsForTotal,
            appelsToday,
            appelsWeek,
            recentDossiers,
            recentFactures,
            lateRecouvrements,
            recentEncaissements,
        ] = await Promise.all([
            this.orm.searchCount("recouvrement.facture", factureDomain),
            this.orm.searchCount("recouvrement.facture", [...factureDomain, ["recouvrement_status", "=", "normal"]]),
            this.orm.searchCount("recouvrement.facture", [...factureDomain, ["recouvrement_status", "=", "precontentieux"]]),
            this.orm.searchCount("recouvrement.facture", [...factureDomain, ["recouvrement_status", "=", "contentieux"]]),
            this.orm.searchCount("recouvrement.facture", [...factureDomain, ["recouvrement_status", "=", "bloque"]]),
            this.orm.searchCount("recouvrement.facture", [...factureDomain, ["recouvrement_status", "=", "recouvre"]]),
            this.orm.searchCount("recouvrement.recouvrement", dossierDomain),
            this.orm.searchCount("recouvrement.recouvrement", [...dossierDomain, ["state", "=", "draft"]]),
            this.orm.searchCount("recouvrement.recouvrement", [...dossierDomain, ["state", "=", "open"]]),
            this.orm.searchCount("recouvrement.recouvrement", [...dossierDomain, ["state", "=", "late"]]),
            this.orm.searchCount("recouvrement.recouvrement", [...dossierDomain, ["state", "=", "blocked"]]),
            this.orm.searchCount("recouvrement.recouvrement", [...dossierDomain, ["state", "=", "closed"]]),
            this.orm.searchRead("recouvrement.recouvrement", [...dossierDomain, ["state", "!=", "closed"]], ["reste_a_recouvrer"]),
            this.orm.searchRead("recouvrement.encaissement", encaissementDomain, ["montant"]),
            this.orm.searchRead(
                "recouvrement.appel",
                [...appelDomain, ["date_appel", ">=", toISODatetime(todayStart)], ["date_appel", "<=", toISODatetime(todayEnd)]],
                ["name", "client_id", "date_appel", "statut"],
                { limit: 8, order: "date_appel asc" }
            ),
            this.orm.searchRead(
                "recouvrement.appel",
                [...appelDomain, ["date_appel", ">=", toISODatetime(todayStart)], ["date_appel", "<=", toISODatetime(weekEnd)]],
                ["date_appel"],
                { limit: 100, order: "date_appel asc" }
            ),
            this.orm.searchRead(
                "recouvrement.recouvrement",
                dossierDomain,
                ["name", "client_id", "reste_a_recouvrer", "prochaine_echeance", "state"],
                { limit: 8, order: "prochaine_echeance asc, id desc" }
            ),
            this.orm.searchRead(
                "recouvrement.facture",
                factureDomain,
                ["name", "client_id", "date_facture", "depot_display", "montant_ttc", "recouvrement_status"],
                { limit: 8, order: "date_facture desc" }
            ),
            this.orm.searchRead(
                "recouvrement.recouvrement",
                [...dossierDomain, ["state", "in", ["late", "blocked"]]],
                ["facture_id", "client_id", "prochaine_echeance", "reste_a_recouvrer"],
                { limit: 8, order: "prochaine_echeance asc" }
            ),
            this.orm.searchRead(
                "recouvrement.encaissement",
                encaissementDomain,
                ["name", "facture_id", "date_operation", "montant"],
                { limit: 8, order: "date_operation desc" }
            ),
        ]);

        const montantAEncaisser = recouvrementsOpen.reduce((sum, item) => sum + (item.reste_a_recouvrer || 0), 0);
        const montantTotalEncaisse = encaissementsForTotal.reduce((sum, item) => sum + (item.montant || 0), 0);
        const appelsATraiter = appelsToday.filter((a) => a.statut !== "realise").length;

        const formatToMDH = (value) => `${formatAmount((value || 0) / 1_000_000)} MDH`;

        this.state.kpis = [
            {
                label: "En retard",
                value: `${lateDossiers + blockedDossiers} dossiers`,
                subLabel: `${openDossiers} precontentieux`,
                icon: "fa-file-text-o",
                actionXmlId: "recouvrement_contentieux.action_recouvrement_recouvrement",
            },
            {
                label: "Actions du jour",
                value: `${appelsToday.length} appels`,
                subLabel: `${appelsATraiter} a traiter`,
                icon: "fa-phone",
                actionXmlId: "recouvrement_contentieux.action_recouvrement_appel",
            },
            {
                label: "A encaisser",
                value: formatToMDH(montantAEncaisser),
                subLabel: `Sur ${totalFactures} factures`,
                icon: "fa-database",
                actionXmlId: "recouvrement_contentieux.action_recouvrement_encaissement",
            },
            {
                label: "Taux de recouvrement",
                value: `${totalFactures ? Math.round((factureRecouvre / totalFactures) * 100) : 0}%`,
                subLabel: `${factureRecouvre}/${totalFactures} factures recouvrees`,
                icon: "fa-line-chart",
                actionXmlId: "recouvrement_contentieux.action_recouvrement_recouvrement",
            },
        ];

        const useFactureScope = this.state.selectedScope === "factures" || !totalDossiers;
        const chartNormal = useFactureScope ? factureNormal : draftDossiers;
        const chartOpen = useFactureScope ? facturePre : openDossiers;
        const chartLate = useFactureScope ? factureContentieux + factureBloque : lateDossiers + blockedDossiers;
        const chartClosed = useFactureScope ? factureRecouvre : closedDossiers;

        this.state.statusBreakdown = [
            { label: "Normal", value: String(chartNormal), tone: "draft" },
            { label: "En retard", value: String(chartOpen), tone: "open" },
            { label: "Contentieux", value: String(chartLate), tone: "late" },
            { label: "Payees", value: String(chartClosed), tone: "closed" },
        ];
        this.state.totalStatus = chartNormal + chartOpen + chartLate + chartClosed;

        const safeTotal = Math.max(this.state.totalStatus, 1);
        const pDraft = Math.round((chartNormal / safeTotal) * 100);
        const pOpen = Math.round((chartOpen / safeTotal) * 100);
        const pLate = Math.round((chartLate / safeTotal) * 100);
        const pClosed = Math.max(0, 100 - (pDraft + pOpen + pLate));
        this.state.donutStyle = `background: conic-gradient(#0c5fad 0 ${pDraft}%, #f7941d ${pDraft}% ${pDraft + pOpen}%, #e04545 ${pDraft + pOpen}% ${pDraft + pOpen + pLate}%, #35aa52 ${pDraft + pOpen + pLate}% 100%);`;

        this.state.recentFactures = recentFactures.map((item) => ({
            id: item.id,
            name: item.name,
            client: item.client_id?.[1] || "-",
            date: formatDate(item.date_facture),
            depot: item.depot_display || "-",
            montant: `${formatAmount(item.montant_ttc)} MAD`,
            status: item.recouvrement_status || "normal",
        }));

        this.state.todayAgenda = appelsToday.slice(0, 5).map((item) => ({
            id: item.id,
            time: new Intl.DateTimeFormat("fr-FR", { hour: "2-digit", minute: "2-digit" }).format(new Date(item.date_appel)),
            title: item.name || `Appel ${item.client_id?.[1] || "Client"}`,
            note: `${item.client_id?.[1] || "-"} - ${item.statut || "brouillon"}`,
        }));

        const weekMap = new Map();
        for (const item of appelsWeek) {
            const dayLabel = new Intl.DateTimeFormat("fr-FR", { weekday: "long", day: "2-digit", month: "2-digit" }).format(new Date(item.date_appel));
            weekMap.set(dayLabel, (weekMap.get(dayLabel) || 0) + 1);
        }
        this.state.weekAgenda = Array.from(weekMap.entries()).slice(0, 5).map(([day, count], index) => ({
            id: index + 1,
            day,
            count: `${count} action${count > 1 ? "s" : ""}`,
        }));

        const statusLabels = {
            normal: "Normal",
            precontentieux: "En retard",
            contentieux: "Contentieux",
            bloque: "Bloque",
            recouvre: "Paye",
        };

        this.state.dossierRows = recentDossiers.map((item) => ({
            id: item.id,
            name: item.name,
            client: item.client_id?.[1] || "-",
            montant: `${formatAmount(item.reste_a_recouvrer)} MAD`,
            date: formatDate(item.prochaine_echeance),
            tone: item.state === "open" ? "open" : item.state === "late" ? "late" : item.state === "blocked" ? "blocked" : item.state === "closed" ? "closed" : "draft",
            status: item.state === "open" ? "En retard" : item.state === "late" ? "Contentieux" : item.state === "blocked" ? "Bloque" : item.state === "closed" ? "Paye" : "Normal",
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

    onDateFromChange(ev) {
        this.state.dateFrom = ev.target.value;
        this.loadDashboard();
    }

    onDateToChange(ev) {
        this.state.dateTo = ev.target.value;
        this.loadDashboard();
    }

    onScopeChange(ev) {
        this.state.selectedScope = ev.target.value;
        this.loadDashboard();
    }

    onStatusChange(ev) {
        this.state.selectedStatus = ev.target.value;
        this.loadDashboard();
    }

    onCommercialChange(ev) {
        this.state.selectedCommercial = ev.target.value;
        this.loadDashboard();
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
