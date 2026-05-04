/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

import { CidButton }     from "../../ui/button/button";
import { CidCard }       from "../../ui/card/card";
import { CidBadge }      from "../../ui/badge/badge";
import { CidKpiCard }    from "../../ui/kpi_card/kpi_card";
import { CidSkeleton }   from "../../ui/skeleton/skeleton";
import { CidEmptyState } from "../../ui/empty_state/empty_state";
import { CidStatusPill } from "../../ui/status_pill/status_pill";

/**
 * EncaissementDetailPage — Détail d'un encaissement + lettrage dynamique
 *
 * Structure :
 *  ┌─────────────────────────────────────────────────┐
 *  │  ← Retour    ENC/2026/00001    [badge état]     │
 *  │  4 KPI cards (montant, alloué, reste, pénalité) │
 *  ├────────────────────────┬────────────────────────┤
 *  │  Infos encaissement    │  Lettrage dynamique     │
 *  │  (client, date, mode)  │  Compteur reste live    │
 *  │                        │  Table factures dispo   │
 *  │                        │  [Valider] [Auto FIFO]  │
 *  └────────────────────────┴────────────────────────┘
 */
export class EncaissementDetailPage extends Component {
    static template = "recouvrement_contentieux.EncaissementDetailPage";
    static components = {
        CidButton, CidCard, CidBadge, CidKpiCard,
        CidSkeleton, CidEmptyState, CidStatusPill,
    };
    static props = { "*": true };

    setup() {
        this.orm           = useService("orm");
        this.toast         = useService("cid_toast");
        this.actionService = useService("action");

        this.state = useState({
            loading:  true,
            saving:   false,
            autoAllouing: false,
            enc:      null,       // données encaissement
            factures: [],         // factures disponibles à lettrer
            lettrages: [],        // lettrages existants [{id, facture_id, montant_affecte, ...}]
            // Allocations en cours saisies par l'user: { factureId: number }
            allocations: {},
        });

        onWillStart(() => this.loadData());
    }

    // ── Computed ─────────────────────────────────────────────────────────────

    get fmt() {
        return v => v != null
            ? new Intl.NumberFormat("fr-FR", { minimumFractionDigits: 2 }).format(v)
            : "—";
    }

    get fmtDate() {
        return v => v ? new Intl.DateTimeFormat("fr-FR").format(new Date(v)) : "—";
    }

    get resteEnCours() {
        if (!this.state.enc) return 0;
        const totalAlloue = Object.values(this.state.allocations)
            .reduce((s, v) => s + (parseFloat(v) || 0), 0);
        return Math.max(0, (this.state.enc.reste_a_allouer || 0) - totalAlloue);
    }

    get resteClass() {
        if (this.resteEnCours === 0) return "text-success";
        if (this.resteEnCours < 0)  return "text-danger";
        return "";
    }

    get totalNewAlloc() {
        return Object.values(this.state.allocations)
            .reduce((s, v) => s + (parseFloat(v) || 0), 0);
    }

    get canSave() {
        return this.totalNewAlloc > 0 && !this.state.saving;
    }

    get etatLabel() {
        return { en_cours: "En cours", solde: "Soldé", en_attente: "En attente" }
            [this.state.enc?.etat_lettrage] || "—";
    }

    get etatVariant() {
        return { en_cours: "warning", solde: "success", en_attente: "neutral" }
            [this.state.enc?.etat_lettrage] || "neutral";
    }

    get modeLabel() {
        return { virement: "Virement", cheque: "Chèque", espece: "Espèces",
                 lcn: "LCN", traite: "Traite" }
            [this.state.enc?.mode_paiement] || this.state.enc?.mode_paiement || "—";
    }

    // ── Chargement ───────────────────────────────────────────────────────────

    async loadData() {
        this.state.loading = true;
        try {
            const encId = this.props.action?.context?.encaissement_id
                       || this.props.action?.params?.encaissement_id;
            if (!encId) {
                this.toast.error("Encaissement non spécifié");
                return;
            }

            const [[enc], factures, lettrages] = await Promise.all([
                this.orm.read(
                    "recouvrement.encaissement", [encId],
                    ["id", "name", "client_id", "montant", "montant_alloue",
                     "reste_a_allouer", "penalite", "etat_lettrage",
                     "date_operation", "code_affaire", "banque", "pole_id",
                     "mode_paiement", "currency_id", "observation",
                     "recouvrement_id", "lettrage_ids"],
                ),
                this.orm.call(
                    "recouvrement.encaissement", "get_factures_disponibles", [encId]
                ),
                this.orm.searchRead(
                    "recouvrement.lettrage",
                    [["encaissement_id", "=", encId]],
                    ["id", "facture_id", "montant_affecte", "date_lettrage"],
                    { order: "date_lettrage asc" },
                ),
            ]);

            this.state.enc      = { ...enc, currency: enc.currency_id?.[1] || "MAD" };
            this.state.factures = factures || [];
            this.state.lettrages = lettrages;
            // Initialiser les allocations à 0 pour chaque facture dispo
            const alloc = {};
            for (const f of factures || []) alloc[f.id] = 0;
            this.state.allocations = alloc;

        } catch (err) {
            this.toast.error("Erreur de chargement", { description: err?.message || "" });
        } finally {
            this.state.loading = false;
        }
    }

    // ── Lettrage ──────────────────────────────────────────────────────────────

    onAllocationInput(factureId, ev) {
        const raw  = parseFloat(ev.target.value) || 0;
        const facture = this.state.factures.find(f => f.id === factureId);
        if (!facture) return;

        // Ne pas dépasser le reste à payer de la facture
        const maxFacture = facture.reste_a_payer || 0;
        // Ne pas dépasser le reste à allouer de l'encaissement
        const autresAllocs = Object.entries(this.state.allocations)
            .filter(([k]) => parseInt(k) !== factureId)
            .reduce((s, [, v]) => s + (parseFloat(v) || 0), 0);
        const maxEnc = Math.max(0, (this.state.enc.reste_a_allouer || 0) - autresAllocs);

        this.state.allocations[factureId] = Math.min(raw, maxFacture, maxEnc);
        // Resync l'input si la valeur a été plafonnée
        ev.target.value = this.state.allocations[factureId];
    }

    async onSaveLettrage() {
        const toSave = Object.entries(this.state.allocations)
            .filter(([, v]) => parseFloat(v) > 0)
            .map(([k, v]) => ({ facture_id: parseInt(k), montant: parseFloat(v) }));

        if (!toSave.length) return;

        this.state.saving = true;
        try {
            for (const item of toSave) {
                await this.orm.call(
                    "recouvrement.encaissement",
                    "appliquer_lettrage",
                    [this.state.enc.id, item.facture_id, item.montant],
                );
            }
            this.toast.success("Lettrage enregistré");
            await this.loadData();
        } catch (err) {
            this.toast.error("Erreur lettrage", { description: err?.message || "" });
        } finally {
            this.state.saving = false;
        }
    }

    async onAutoFifo() {
        this.state.autoAllouing = true;
        try {
            await this.orm.call(
                "recouvrement.encaissement", "auto_allouer_fifo", [this.state.enc.id]
            );
            this.toast.success("Auto-allocation FIFO effectuée");
            await this.loadData();
        } catch (err) {
            this.toast.error("Erreur FIFO", { description: err?.message || "" });
        } finally {
            this.state.autoAllouing = false;
        }
    }

    async onDeleteLettrage(lettrageId) {
        try {
            await this.orm.unlink("recouvrement.lettrage", [lettrageId]);
            this.toast.success("Lettrage supprimé");
            await this.loadData();
        } catch (err) {
            this.toast.error("Erreur suppression", { description: err?.message || "" });
        }
    }

    onBack() {
        this.actionService.doAction({
            type:    "ir.actions.client",
            tag:     "recouvrement_contentieux.encaissements_list_page",
            target:  "current",
        });
    }
}

registry.category("actions").add(
    "recouvrement_contentieux.encaissement_detail_page",
    EncaissementDetailPage,
);
