/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

import { CidButton } from "../../ui/button/button";
import { CidCard } from "../../ui/card/card";
import { CidBadge } from "../../ui/badge/badge";
import { CidStatusPill } from "../../ui/status_pill/status_pill";
import { CidSkeleton } from "../../ui/skeleton/skeleton";
import { CidEmptyState } from "../../ui/empty_state/empty_state";
import { CidDialog } from "../../ui/dialog/dialog";

/**
 * Page « Exécution d'une action de relance »
 *
 * Per cahier de charge :
 *   « Lorsque l'agent clique sur une facture, le système n'ouvre pas un
 *     petit pop-up, mais navigue vers une nouvelle page de saisie dédiée
 *     et spacieuse.
 *
 *     Pour un email : Cette page affiche l'éditeur de texte riche, l'objet,
 *     le destinataire (issu du client), et le corps de l'email est
 *     pré-généré avec les détails du lot de factures de ce dossier.
 *
 *     Pour un appel : La page affiche le script d'appel, le numéro,
 *     et les boutons de qualification du compte-rendu (Promesse de paiement,
 *     Report, Litige). »
 *
 * URL : action client recouvrement_contentieux.action_execution_page
 *       avec context { action_id: <id> }
 */
export class ActionExecutionPage extends Component {
    static template = "recouvrement_contentieux.ActionExecutionPage";
    static components = {
        CidButton, CidCard, CidBadge, CidStatusPill, CidSkeleton,
        CidEmptyState, CidDialog,
    };
    static props = { "*": true };

    setup() {
        this.orm = useService("orm");
        this.toast = useService("cid_toast");
        this.actionService = useService("action");

        this.state = useState({
            loading: true,
            action: null,
            client: null,
            dossier: null,
            factures: [],            // factures du dossier pour ce client
            history: [],             // actions passées sur ce client/dossier

            // Form state pour appel
            duree_minutes: 0,
            notes_appel: "",
            action_prise: "aucune",

            // Form state pour email
            sujet: "",
            corps: "",
            destinataire: "",

            // Modal de qualification appel
            showQualifyDialog: false,

            saving: false,
            sending: false,
        });

        onWillStart(async () => {
            await this.loadData();
        });
    }

    async loadData() {
        this.state.loading = true;
        try {
            const actionId = this.props.action?.context?.action_id
                || this.props.action?.params?.action_id;
            if (!actionId) {
                this.toast.error("Aucune action spécifiée");
                this.state.loading = false;
                return;
            }

            // Lecture de l'action
            const [action] = await this.orm.read(
                "recouvrement.action",
                [actionId],
                ["id", "name", "action_type", "comment", "state",
                 "mandatory_date", "date_done", "client_id", "recouvrement_id",
                 "action_template_id", "responsible_id",
                 "duree_minutes", "notes_appel", "action_prise",
                 "destinataire_email", "sujet_email", "corps_email", "email_status",
                 "is_overdue", "priority", "planned_datetime"],
            );
            if (!action) {
                this.toast.error("Action introuvable");
                this.state.loading = false;
                return;
            }
            this.state.action = action;

            // Init form state
            this.state.duree_minutes = action.duree_minutes || 0;
            this.state.notes_appel = action.notes_appel || "";
            this.state.action_prise = action.action_prise || "aucune";
            this.state.sujet = action.sujet_email || action.name || "";
            this.state.corps = action.corps_email || "";
            this.state.destinataire = action.destinataire_email || "";

            // Lecture client
            if (action.client_id) {
                const [client] = await this.orm.read(
                    "res.partner",
                    [action.client_id[0]],
                    ["id", "name", "email", "phone", "client_type_id"],
                );
                this.state.client = client;
                if (!this.state.destinataire && client.email) {
                    this.state.destinataire = client.email;
                }
                // Note: champ 'mobile' non disponible dans cette config Odoo
            }

            // Lecture dossier + factures du client dans ce dossier
            if (action.recouvrement_id) {
                const [dossier] = await this.orm.read(
                    "recouvrement.recouvrement",
                    [action.recouvrement_id[0]],
                    ["id", "name", "phase_courante", "procedure_id",
                     "facture_ids", "reste_a_recouvrer", "currency_id"],
                );
                this.state.dossier = dossier;

                if (dossier.facture_ids?.length) {
                    const factures = await this.orm.read(
                        "recouvrement.facture",
                        dossier.facture_ids,
                        ["id", "name", "code_affaire", "client_id",
                         "date_facture", "montant_ttc", "reste_a_payer",
                         "date_depot_client", "statut_interface", "recouvrement_status"],
                    );
                    // Filter pour ce client
                    this.state.factures = factures.filter(
                        (f) => f.client_id?.[0] === action.client_id?.[0],
                    );
                }
            }

            // Pré-remplir le corps email si vide et type = email/courrier
            if (
                !this.state.corps
                && ["email", "courrier", "mise_en_demeure"].includes(action.action_type)
            ) {
                this.state.corps = this._buildDefaultEmailBody();
            }

            // Historique : actions passées sur ce client + dossier
            if (action.recouvrement_id && action.client_id) {
                const history = await this.orm.searchRead(
                    "recouvrement.action",
                    [
                        ["recouvrement_id", "=", action.recouvrement_id[0]],
                        ["client_id", "=", action.client_id[0]],
                        ["id", "!=", actionId],
                        ["state", "=", "done"],
                    ],
                    ["id", "name", "action_type", "date_done", "action_prise",
                     "duree_minutes", "responsible_id"],
                    { limit: 10, order: "date_done desc" },
                );
                this.state.history = history;
            }
        } catch (err) {
            console.error("Erreur chargement action :", err);
            this.toast.error("Erreur de chargement");
        } finally {
            this.state.loading = false;
        }
    }

    _buildDefaultEmailBody() {
        const lines = [];
        lines.push(`<p>Bonjour,</p>`);
        lines.push(
            `<p>Sauf erreur de notre part, nos services indiquent que la (les) `
            + `facture(s) suivante(s) restent à régler :</p>`,
        );
        lines.push(`<ul>`);
        for (const f of this.state.factures.filter((x) => x.reste_a_payer > 0)) {
            lines.push(
                `<li>Facture <strong>${f.name}</strong>`
                + (f.code_affaire ? ` (${f.code_affaire})` : "")
                + ` — Reste à payer : <strong>${this.fmt(f.reste_a_payer)} DH</strong>`
                + `</li>`,
            );
        }
        lines.push(`</ul>`);
        lines.push(
            `<p>Nous vous remercions de bien vouloir procéder au règlement `
            + `dans les meilleurs délais.</p>`,
        );
        lines.push(`<p>Cordialement,<br/>Service Recouvrement — CID Développement</p>`);
        return lines.join("\n");
    }

    /* -----------------------------------------------------------------
     *  Actions
     * ----------------------------------------------------------------- */
    async _saveActionFields() {
        const a = this.state.action;
        const vals = {};
        if (a.action_type === "appel") {
            vals.duree_minutes = Number(this.state.duree_minutes) || 0;
            vals.notes_appel = this.state.notes_appel;
            vals.action_prise = this.state.action_prise;
        } else {
            vals.sujet_email = this.state.sujet;
            vals.corps_email = this.state.corps;
            vals.destinataire_email = this.state.destinataire;
        }
        await this.orm.write("recouvrement.action", [a.id], vals);
    }

    async onSendEmail() {
        if (!this.state.destinataire) {
            this.toast.error("Email destinataire manquant");
            return;
        }
        if (!this.state.sujet) {
            this.toast.error("Objet manquant");
            return;
        }
        this.state.sending = true;
        try {
            await this._saveActionFields();
            await this.orm.call(
                "recouvrement.action",
                "action_envoyer_email",
                [this.state.action.id],
            );
            this.toast.success("Email envoyé", {
                description: `Action marquée comme réalisée.`,
            });
            await this.loadData();
            // Retour vers le dossier après envoi
            setTimeout(() => this.onBackToDossier(), 800);
        } catch (err) {
            this.toast.error("Échec de l'envoi", {
                description: err?.message?.message || err?.message || "",
                duration: 8000,
            });
        } finally {
            this.state.sending = false;
        }
    }

    onSaveDraft() {
        // Pour email : sauvegarde du brouillon sans envoyer
        this._saveActionFields().then(() => {
            this.toast.info("Brouillon enregistré");
        }).catch(() => {
            this.toast.error("Échec de l'enregistrement");
        });
    }

    onOpenQualify() {
        this.state.showQualifyDialog = true;
    }
    onCloseQualify() {
        this.state.showQualifyDialog = false;
    }

    async onQualifyAction(prise) {
        this.state.action_prise = prise;
        this.state.showQualifyDialog = false;
        await this._saveActionFields();
        // Si "non_joignable" → on lance directement le report J+1
        if (prise === "non_joignable") {
            await this.onReportJ1();
            return;
        }
        // Sinon, on marque l'action comme réalisée
        this.state.saving = true;
        try {
            await this.orm.call(
                "recouvrement.action",
                "action_done",
                [this.state.action.id],
            );
            this.toast.success("Appel qualifié", {
                description: this._qualifyLabel(prise),
            });
            setTimeout(() => this.onBackToDossier(), 700);
        } catch (err) {
            this.toast.error("Erreur");
        } finally {
            this.state.saving = false;
        }
    }

    async onReportJ1() {
        try {
            await this._saveActionFields();
            await this.orm.call(
                "recouvrement.action",
                "action_reporter",
                [this.state.action.id],
            );
            this.toast.success("Action reportée à J+1", {
                description: "Une nouvelle action a été générée pour demain.",
            });
            setTimeout(() => this.onBackToDossier(), 700);
        } catch (err) {
            this.toast.error("Erreur");
        }
    }

    /* -----------------------------------------------------------------
     *  Navigation
     * ----------------------------------------------------------------- */
    onBackToDossier() {
        if (this.state.dossier?.id) {
            this.actionService.doAction({
                type: "ir.actions.client",
                tag: "recouvrement_contentieux.dossier_detail_page",
                context: { dossier_id: this.state.dossier.id },
                target: "current",
            });
        } else {
            this.actionService.doAction(
                "recouvrement_contentieux.action_recouvrement_recouvrement",
            );
        }
    }

    /* -----------------------------------------------------------------
     *  Helpers
     * ----------------------------------------------------------------- */
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
    _qualifyLabel(p) {
        return {
            paiement: "Promesse de paiement enregistrée",
            plan_paiement: "Plan de paiement noté",
            dialogue: "Dialogue établi",
            non_joignable: "Client non joignable — report J+1",
            litige: "Litige déclaré",
            escalade: "Escalade enregistrée",
            aucune: "Aucune action particulière",
        }[p] || p;
    }

    get isEmailLike() {
        return ["email", "courrier", "mise_en_demeure"].includes(
            this.state.action?.action_type,
        );
    }
    get isCallLike() {
        return this.state.action?.action_type === "appel";
    }
    get isDone() {
        return this.state.action?.state === "done";
    }
    get totalReste() {
        return this.state.factures.reduce(
            (s, f) => s + (f.reste_a_payer || 0), 0,
        );
    }
}

registry
    .category("actions")
    .add(
        "recouvrement_contentieux.action_execution_page",
        ActionExecutionPage,
    );