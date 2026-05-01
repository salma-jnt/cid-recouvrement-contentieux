/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

import { CidButton } from "../../ui/button/button";
import { CidCard } from "../../ui/card/card";
import { CidBadge } from "../../ui/badge/badge";
import { CidStatusPill } from "../../ui/status_pill/status_pill";
import { CidKpiCard } from "../../ui/kpi_card/kpi_card";
import { CidEmptyState } from "../../ui/empty_state/empty_state";
import { CidSkeleton } from "../../ui/skeleton/skeleton";

/**
 * Dashboard CID Recouvrement — refonte complète
 *
 * CORRECTION Odoo 17+/19 :
 *   orm.readGroup() a été supprimé du service ORM JavaScript.
 *   Remplacement : this.orm.call(model, "read_group", [], { domain, fields, groupby })
 *   qui appelle directement la méthode Python read_group via RPC.
 */
export class CidDashboard extends Component {
    static template = "recouvrement_contentieux.CidDashboard";
    static components = {
        CidButton, CidCard, CidBadge, CidStatusPill,
        CidKpiCard, CidEmptyState, CidSkeleton,
    };

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.toast = useService("cid_toast");

        this.state = useState({
            loading: true,
            kpis: {
                montantTotal: 0,
                resteARecouvrer: 0,
                encaisseSemaine: 0,
                dossiersOuverts: 0,
                actionsAujourdhui: 0,
                actionsEnRetard: 0,
            },
            actionsAujourdhui: [],
            actionsSemaine: [],
            repartitionStatut: { vert: 0, orange: 0, rouge: 0, mauve: 0 },
            topDossiersRisque: [],
        });

        onWillStart(async () => {
            await this.loadDashboard();
        });
    }

    async loadDashboard() {
        this.state.loading = true;
        try {
            await Promise.all([
                this._loadKpis(),
                this._loadActions(),
                this._loadRepartition(),
                this._loadTopRisque(),
            ]);
        } catch (err) {
            console.error("Dashboard load error:", err);
            this.toast.error("Erreur de chargement du tableau de bord");
        } finally {
            this.state.loading = false;
        }
    }

    async _loadKpis() {
        // ✅ CORRECTION : orm.readGroup() supprimé en Odoo 17+
        // → remplacé par orm.call(model, "read_group", [], { domain, fields, groupby })
        const grpMontants = await this.orm.call(
            "recouvrement.facture",
            "read_group",
            [],
            {
                domain: [],
                fields: ["montant_ttc:sum", "reste_a_payer:sum"],
                groupby: [],
            },
        );
        if (grpMontants[0]) {
            this.state.kpis.montantTotal = grpMontants[0].montant_ttc || 0;
            this.state.kpis.resteARecouvrer = grpMontants[0].reste_a_payer || 0;
        }

        // Encaissé sur les 7 derniers jours
        const date7 = new Date();
        date7.setDate(date7.getDate() - 7);
        const dateStr = date7.toISOString().split("T")[0];

        // ✅ CORRECTION : même remplacement
        const grpEnc = await this.orm.call(
            "recouvrement.encaissement",
            "read_group",
            [],
            {
                domain: [["date_operation", ">=", dateStr]],
                fields: ["montant:sum"],
                groupby: [],
            },
        );
        if (grpEnc[0]) {
            this.state.kpis.encaisseSemaine = grpEnc[0].montant || 0;
        }

        // Dossiers ouverts — searchCount inchangé ✓
        this.state.kpis.dossiersOuverts = await this.orm.searchCount(
            "recouvrement.recouvrement",
            [["state", "in", ["ouvert", "en_cours", "en_retard"]]],
        );

        // Actions du jour + en retard — searchCount inchangé ✓
        const today = new Date().toISOString().split("T")[0];
        this.state.kpis.actionsAujourdhui = await this.orm.searchCount(
            "recouvrement.action",
            [
                ["state", "in", ["todo", "reporte"]],
                ["mandatory_date", "=", today],
            ],
        );
        this.state.kpis.actionsEnRetard = await this.orm.searchCount(
            "recouvrement.action",
            [
                ["state", "in", ["todo", "reporte"]],
                ["mandatory_date", "<", today],
            ],
        );
    }

    async _loadActions() {
        const today = new Date().toISOString().split("T")[0];
        const date7 = new Date();
        date7.setDate(date7.getDate() + 7);
        const date7Str = date7.toISOString().split("T")[0];

        // searchRead inchangé ✓
        const todayActions = await this.orm.searchRead(
            "recouvrement.action",
            [
                ["state", "in", ["todo", "reporte"]],
                ["mandatory_date", "=", today],
            ],
            ["id", "name", "action_type", "client_id", "mandatory_date",
             "responsible_id", "is_overdue", "recouvrement_id"],
            { limit: 8, order: "mandatory_date asc, id" },
        );
        this.state.actionsAujourdhui = todayActions;

        const weekActions = await this.orm.searchRead(
            "recouvrement.action",
            [
                ["state", "in", ["todo", "reporte"]],
                ["mandatory_date", ">", today],
                ["mandatory_date", "<=", date7Str],
            ],
            ["id", "name", "action_type", "client_id", "mandatory_date",
             "responsible_id", "is_overdue", "recouvrement_id"],
            { limit: 8, order: "mandatory_date asc, id" },
        );
        this.state.actionsSemaine = weekActions;
    }

    async _loadRepartition() {
        // ✅ CORRECTION : même remplacement
        const grp = await this.orm.call(
            "recouvrement.facture",
            "read_group",
            [],
            {
                domain: [["reste_a_payer", ">", 0]],
                fields: ["statut_interface", "id:count"],
                groupby: ["statut_interface"],
            },
        );
        const rep = { vert: 0, orange: 0, rouge: 0, mauve: 0 };
        for (const g of grp) {
            const k = g.statut_interface;
            if (k && k in rep) rep[k] = g.statut_interface_count || g.__count || 0;
        }
        this.state.repartitionStatut = rep;
    }

    async _loadTopRisque() {
        // searchRead inchangé ✓
        const dossiers = await this.orm.searchRead(
            "recouvrement.recouvrement",
            [["state", "=", "en_retard"]],
            ["id", "name", "phase_courante", "reste_a_recouvrer",
             "nombre_factures", "prochaine_echeance"],
            { limit: 5, order: "reste_a_recouvrer desc" },
        );
        this.state.topDossiersRisque = dossiers;
    }

    /* ----- Helpers ----- */
    fmt(n, decimals = 0) {
        return new Intl.NumberFormat("fr-FR", {
            minimumFractionDigits: decimals,
            maximumFractionDigits: decimals,
        }).format(Number(n) || 0);
    }
    fmtCompact(n) {
        const v = Number(n) || 0;
        if (Math.abs(v) >= 1e9) return `${(v / 1e9).toFixed(1)} Mds`;
        if (Math.abs(v) >= 1e6) return `${(v / 1e6).toFixed(1)} M`;
        if (Math.abs(v) >= 1e3) return `${(v / 1e3).toFixed(0)} k`;
        return this.fmt(v);
    }
    fmtDate(s) {
        if (!s) return "-";
        const d = new Date(s);
        if (isNaN(d.getTime())) return s;
        return new Intl.DateTimeFormat("fr-FR").format(d);
    }
    actionTypeIcon(t) {
        return {
            appel: "fa-phone",
            email: "fa-envelope-o",
            courrier: "fa-file-text-o",
            mise_en_demeure: "fa-gavel",
            contentieux: "fa-balance-scale",
        }[t] || "fa-tasks";
    }
    actionTypeLabel(t) {
        return {
            appel: "Appel",
            email: "Email",
            courrier: "Courrier",
            mise_en_demeure: "Mise en demeure",
            contentieux: "Contentieux",
        }[t] || t;
    }

    get repartitionTotal() {
        const r = this.state.repartitionStatut;
        return (r.vert || 0) + (r.orange || 0) + (r.rouge || 0) + (r.mauve || 0);
    }
    repartitionPct(color) {
        const t = this.repartitionTotal;
        if (!t) return 0;
        return ((this.state.repartitionStatut[color] || 0) / t) * 100;
    }

    /* ----- Click handlers ----- */
    onActionClick(a) {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "recouvrement.action",
            res_id: a.id,
            views: [[false, "form"]],
            target: "current",
        });
    }
    onSeeAllActions() {
        this.actionService.doAction(
            "recouvrement_contentieux.action_recouvrement_action_calendar",
        );
    }
    onSeeFactures(filter) {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "recouvrement.facture",
            views: [[false, "list"], [false, "form"]],
            domain: filter ? [["statut_interface", "=", filter]] : [],
            target: "current",
        });
    }
    onDossierClick(dossier) {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "recouvrement.recouvrement",
            res_id: dossier.id,
            views: [[false, "form"]],
            target: "current",
        });
    }
    onImportFactures() {
        this.actionService.doAction(
            "recouvrement_contentieux.action_recouvrement_import_factures_modern",
        );
    }
    onSeeDossiers() {
        this.actionService.doAction(
            "recouvrement_contentieux.action_recouvrement_recouvrement",
        );
    }
}

registry.category("actions").add(
    "recouvrement_contentieux.dashboard",
    CidDashboard,
);