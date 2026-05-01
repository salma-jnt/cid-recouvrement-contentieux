/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

import { CidButton } from "../../ui/button/button";
import { CidCard } from "../../ui/card/card";
import { CidBadge } from "../../ui/badge/badge";
import { CidStatusPill } from "../../ui/status_pill/status_pill";
import { CidStepper } from "../../ui/stepper/stepper";
import { CidKpiCard } from "../../ui/kpi_card/kpi_card";
import { CidSkeleton } from "../../ui/skeleton/skeleton";

/**
 * Page « Détail d'un dossier de recouvrement »
 *
 * Affiche :
 *   - Header avec KPIs (TTC, encaissé, reste, nb factures, nb clients, échéance)
 *   - Stepper horizontal : phases de la procédure avec couleurs et état done/current
 *   - Bloc factures groupées par client
 *   - Pour chaque facture, bouton "Action" qui ouvre la page d'exécution
 *     (appel ou email selon la phase courante)
 */
export class DossierDetailPage extends Component {
    static template = "recouvrement_contentieux.DossierDetailPage";
    static components = {
        CidButton, CidCard, CidBadge, CidStatusPill, CidStepper,
        CidKpiCard, CidSkeleton,
    };
    static props = { "*": true };

    setup() {
        this.orm = useService("orm");
        this.toast = useService("cid_toast");
        this.actionService = useService("action");

        this.state = useState({
            loading: true,
            dossier: null,
            factures: [],         // group by client
            actions: [],
            phases: [],           // for stepper
            activeTab: "factures",
        });

        onWillStart(async () => {
            await this.loadData();
        });
    }

    async loadData() {
        this.state.loading = true;
        try {
            const dossierId = this.props.action?.context?.dossier_id
                || this.props.action?.params?.dossier_id;
            if (!dossierId) {
                this.toast.error("Aucun dossier spécifié");
                this.state.loading = false;
                return;
            }

            // Lecture dossier
            const [dossier] = await this.orm.read(
                "recouvrement.recouvrement",
                [dossierId],
                ["id", "name", "state", "procedure_id", "phase_courante",
                 "date_depot_groupe", "prochaine_echeance", "last_action_date",
                 "nombre_factures", "nombre_clients", "montant_ttc",
                 "montant_encaisse", "reste_a_recouvrer", "currency_id",
                 "facture_ids", "action_ids", "motif_blocage"],
            );
            if (!dossier) {
                this.toast.error("Dossier introuvable");
                this.state.loading = false;
                return;
            }
            this.state.dossier = {
                ...dossier,
                procedure_name: dossier.procedure_id?.[1] || "",
                currency: dossier.currency_id?.[1] || "DH",
            };

            // Factures
            const factures = await this.orm.read(
                "recouvrement.facture",
                dossier.facture_ids,
                ["id", "name", "code_affaire", "client_id", "date_facture",
                 "date_depot_client", "montant_ttc", "montant_paye",
                 "reste_a_payer", "recouvrement_status", "statut_interface"],
            );
            // group by client
            const groups = {};
            for (const f of factures) {
                const cid = f.client_id?.[0] || 0;
                const cname = f.client_id?.[1] || "—";
                if (!groups[cid]) groups[cid] = { client_id: cid, client_name: cname, factures: [], total: 0, reste: 0 };
                groups[cid].factures.push(f);
                groups[cid].total += f.montant_ttc || 0;
                groups[cid].reste += f.reste_a_payer || 0;
            }
            this.state.factures = Object.values(groups);

            // Actions
            const actions = await this.orm.read(
                "recouvrement.action",
                dossier.action_ids,
                ["id", "name", "action_type", "client_id", "state",
                 "mandatory_date", "date_done", "is_overdue",
                 "action_template_id", "responsible_id"],
            );
            this.state.actions = actions;

            // Build stepper depuis les action templates de la procédure
            const procedureId = dossier.procedure_id?.[0];
            if (procedureId) {
                const templates = await this.orm.searchRead(
                    "recouvrement.action.template",
                    [["procedure_id", "=", procedureId]],
                    ["id", "name", "sequence", "delay", "action_type",
                     "statut_interface_cible"],
                    { order: "sequence asc, id asc" },
                );
                // Phase status : déduit en regardant les actions du dossier
                this.state.phases = templates.map((t) => {
                    const matching = actions.filter(
                        (a) => a.action_template_id?.[0] === t.id,
                    );
                    let status = "pending";
                    if (matching.length > 0) {
                        const allDone = matching.every((a) => a.state === "done");
                        const someTodo = matching.some(
                            (a) => a.state === "todo" || a.state === "reporte",
                        );
                        if (allDone) status = "done";
                        else if (someTodo) status = "current";
                    }
                    // Subtitle = J+delay
                    const date = matching[0]?.mandatory_date || "";
                    return {
                        id: t.id,
                        label: t.name,
                        subtitle: t.action_type,
                        date: date ? this.fmtDate(date) : `J+${t.delay}`,
                        status,
                        color: t.statut_interface_cible,
                    };
                });
                // Set "current" only on the first one that's current
                let currentSet = false;
                for (let i = 0; i < this.state.phases.length; i++) {
                    if (this.state.phases[i].status === "current" && currentSet) {
                        this.state.phases[i].status = "pending";
                    } else if (this.state.phases[i].status === "current") {
                        currentSet = true;
                    }
                }
            }
        } catch (err) {
            console.error("Erreur chargement dossier :", err);
            this.toast.error("Erreur de chargement");
        } finally {
            this.state.loading = false;
        }
    }

    get currentPhaseIndex() {
        return Math.max(
            0,
            this.state.phases.findIndex((p) => p.status === "current"),
        );
    }

    get statePill() {
        if (!this.state.dossier) return { color: "neutral", label: "" };
        return {
            ouvert: { color: "info", label: "Ouvert" },
            en_cours: { color: "warning", label: "En cours" },
            en_retard: { color: "danger", label: "En retard" },
            bloque: { color: "danger", label: "Bloqué" },
            solde: { color: "success", label: "Soldé" },
        }[this.state.dossier.state] || { color: "neutral", label: this.state.dossier.state };
    }

    onTab(tab) {
        this.state.activeTab = tab;
    }

    onActionClick(action) {
        // Phase 5 : ouvrira la page d'exécution (page action_execution)
        // Pour l'instant on fait un fallback vers le form Odoo
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "recouvrement.action",
            res_id: action.id,
            views: [[false, "form"]],
            target: "current",
        });
    }

    async onActionDone(action) {
        try {
            await this.orm.call("recouvrement.action", "action_done", [action.id]);
            this.toast.success("Action marquée comme réalisée");
            await this.loadData();
        } catch (err) {
            this.toast.error("Erreur", { description: err?.message?.message || "" });
        }
    }

    async onActionReport(action) {
        try {
            await this.orm.call("recouvrement.action", "action_reporter", [action.id]);
            this.toast.success("Action reportée à J+1", {
                description: "Une nouvelle action a été générée.",
            });
            await this.loadData();
        } catch (err) {
            this.toast.error("Erreur", { description: err?.message?.message || "" });
        }
    }

    onBack() {
        this.actionService.doAction(
            "recouvrement_contentieux.action_recouvrement_recouvrement",
        );
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

    actionTypeIcon(t) {
        return {
            appel: "fa-phone",
            email: "fa-envelope-o",
            courrier: "fa-file-text-o",
            mise_en_demeure: "fa-gavel",
            contentieux: "fa-balance-scale",
        }[t] || "fa-tasks";
    }

    fmt(n) {
        return new Intl.NumberFormat("fr-FR", {
            minimumFractionDigits: 0,
            maximumFractionDigits: 2,
        }).format(Number(n) || 0);
    }

    fmtDate(s) {
        if (!s) return "-";
        const d = new Date(s);
        if (isNaN(d.getTime())) return s;
        return new Intl.DateTimeFormat("fr-FR").format(d);
    }
}

registry
    .category("actions")
    .add(
        "recouvrement_contentieux.dossier_detail_page",
        DossierDetailPage,
    );
