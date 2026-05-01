/** @odoo-module **/

import { Component, useState, onWillStart, useEffect } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

import { CidButton } from "../../ui/button/button";
import { CidCard } from "../../ui/card/card";
import { CidBadge } from "../../ui/badge/badge";
import { CidStatusPill } from "../../ui/status_pill/status_pill";
import { CidEmptyState } from "../../ui/empty_state/empty_state";
import { CidSkeleton } from "../../ui/skeleton/skeleton";

/**
 * Page « Lettrage d'un encaissement » — chapitre 5 du cahier
 *
 * Workflow exact du cahier :
 *   1. L'agent ouvre un encaissement
 *   2. Il sélectionne le client (déjà préremplie sur cette page)
 *   3. Le système affiche UNIQUEMENT les factures non soldées du client
 *   4. Compteur Reste à allouer affiché en haut, qui DIMINUE EN TEMPS RÉEL
 *      au fur et à mesure que l'agent saisit des montants
 *   5. Validation côté UI : jamais dépasser le reste à allouer ni le reste à payer
 *   6. Au save : création des recouvrement.lettrage côté serveur
 *
 * URL : ouverte par action client recouvrement_contentieux.encaissement_lettrage_page
 *       avec dans le contexte { encaissement_id: <id> }
 */
export class EncaissementLettragePage extends Component {
    static template = "recouvrement_contentieux.EncaissementLettragePage";
    static components = {
        CidButton, CidCard, CidBadge, CidStatusPill, CidEmptyState, CidSkeleton,
    };
    static props = { "*": true };

    setup() {
        this.orm = useService("orm");
        this.toast = useService("cid_toast");
        this.actionService = useService("action");

        this.state = useState({
            loading: true,
            saving: false,
            encaissement: null,    // {id, name, client_id, client_name, montant, montant_alloue, reste_a_allouer, currency}
            factures: [],          // [{id, name, code_affaire, date, ttc, paye, reste, statut_interface, ...}]
            // Allocation en cours, indexée par facture id : { [factureId]: number }
            allocations: {},
        });

        onWillStart(async () => {
            await this.loadData();
        });
    }

    /* -----------------------------------------------------------------
     *  Loading
     * ----------------------------------------------------------------- */
    async loadData() {
        this.state.loading = true;
        try {
            const encId = this.props.action?.context?.encaissement_id
                || this.props.action?.params?.encaissement_id;
            if (!encId) {
                this.toast.error("Encaissement non spécifié");
                this.state.loading = false;
                return;
            }

            // 1) Lire l'encaissement
            const [enc] = await this.orm.read(
                "recouvrement.encaissement",
                [encId],
                ["id", "name", "client_id", "montant", "montant_alloue",
                 "reste_a_allouer", "etat_lettrage", "date_operation",
                 "code_affaire", "banque", "mode_paiement", "currency_id"],
            );

            if (!enc) {
                this.toast.error("Encaissement introuvable");
                this.state.loading = false;
                return;
            }

            this.state.encaissement = {
                id: enc.id,
                name: enc.name,
                client_id: enc.client_id?.[0] || enc.client_id,
                client_name: enc.client_id?.[1] || "",
                montant: enc.montant,
                montant_alloue: enc.montant_alloue,
                reste_a_allouer: enc.reste_a_allouer,
                etat_lettrage: enc.etat_lettrage,
                date_operation: enc.date_operation,
                code_affaire: enc.code_affaire,
                banque: enc.banque,
                mode_paiement: enc.mode_paiement,
                currency: enc.currency_id?.[1] || "DH",
            };

            // 2) Charger les factures éligibles via la méthode RPC dédiée
            const factures = await this.orm.call(
                "recouvrement.encaissement",
                "get_factures_disponibles",
                [encId],
            );

            this.state.factures = factures.map((f) => ({
                ...f,
                _suggestion: 0,    // proposition auto = 0 par défaut
            }));

            // Pré-allocations vides
            for (const f of this.state.factures) {
                if (!(f.id in this.state.allocations)) {
                    this.state.allocations[f.id] = 0;
                }
            }
        } catch (err) {
            console.error("Erreur chargement encaissement :", err);
            this.toast.error("Erreur de chargement", {
                description: err?.message?.message || err?.message || "",
            });
        } finally {
            this.state.loading = false;
        }
    }

    /* -----------------------------------------------------------------
     *  Computed dynamiques (live)
     * ----------------------------------------------------------------- */
    get totalAlloueLive() {
        return Object.values(this.state.allocations).reduce(
            (s, v) => s + (Number(v) || 0), 0,
        );
    }

    get resteALlouerLive() {
        if (!this.state.encaissement) return 0;
        return Math.max(
            (this.state.encaissement.montant || 0)
            - (this.state.encaissement.montant_alloue || 0)
            - this.totalAlloueLive,
            0,
        );
    }

    get progressPct() {
        if (!this.state.encaissement || this.state.encaissement.montant <= 0) return 0;
        const total = (this.state.encaissement.montant_alloue || 0) + this.totalAlloueLive;
        return Math.min(100, (total / this.state.encaissement.montant) * 100);
    }

    get isOverflow() {
        if (!this.state.encaissement) return false;
        const total = (this.state.encaissement.montant_alloue || 0) + this.totalAlloueLive;
        return total > this.state.encaissement.montant + 0.01;
    }

    get hasPendingAllocations() {
        return this.totalAlloueLive > 0;
    }

    /* -----------------------------------------------------------------
     *  Actions sur les inputs
     * ----------------------------------------------------------------- */
    onAllocChange(factureId, ev) {
        const facture = this.state.factures.find((f) => f.id === factureId);
        if (!facture) return;

        const raw = ev.target.value;
        let val = Number(raw);
        if (isNaN(val) || val < 0) val = 0;

        // Cap max : ne dépasse jamais reste_a_payer de la facture
        if (val > facture.reste_a_payer) {
            val = facture.reste_a_payer;
            this.toast.warning(
                `Plafond facture atteint`,
                { description: `Reste à payer : ${this.fmt(facture.reste_a_payer)}` },
            );
        }

        // Cap soft : reste à allouer (en tenant compte des autres allocations)
        const otherAlloc = Object.entries(this.state.allocations)
            .filter(([k]) => Number(k) !== factureId)
            .reduce((s, [, v]) => s + (Number(v) || 0), 0);

        const dispo = (this.state.encaissement.montant || 0)
            - (this.state.encaissement.montant_alloue || 0)
            - otherAlloc;

        if (val > dispo) {
            val = Math.max(dispo, 0);
            this.toast.warning(
                `Reste à allouer dépassé`,
                { description: `Disponible : ${this.fmt(dispo)}` },
            );
        }

        this.state.allocations[factureId] = val;
    }

    onMaxClick(factureId) {
        const facture = this.state.factures.find((f) => f.id === factureId);
        if (!facture) return;

        const otherAlloc = Object.entries(this.state.allocations)
            .filter(([k]) => Number(k) !== factureId)
            .reduce((s, [, v]) => s + (Number(v) || 0), 0);

        const dispo = (this.state.encaissement.montant || 0)
            - (this.state.encaissement.montant_alloue || 0)
            - otherAlloc;

        this.state.allocations[factureId] = Math.min(dispo, facture.reste_a_payer);
    }

    onClearLine(factureId) {
        this.state.allocations[factureId] = 0;
    }

    onAutoAllouer() {
        // FIFO côté UI : remplit les factures les plus anciennes en premier
        let restant = this.state.encaissement.reste_a_allouer;
        const newAllocs = { ...this.state.allocations };
        // reset
        for (const f of this.state.factures) newAllocs[f.id] = 0;

        const sorted = [...this.state.factures].sort((a, b) => {
            return (a.date_facture || "").localeCompare(b.date_facture || "");
        });

        for (const f of sorted) {
            if (restant <= 0) break;
            const take = Math.min(restant, f.reste_a_payer);
            if (take > 0) {
                newAllocs[f.id] = take;
                restant -= take;
            }
        }

        this.state.allocations = newAllocs;
        this.toast.info("Auto-allocation FIFO appliquée");
    }

    onResetAll() {
        for (const f of this.state.factures) {
            this.state.allocations[f.id] = 0;
        }
    }

    /* -----------------------------------------------------------------
     *  Save
     * ----------------------------------------------------------------- */
    async onSave() {
        if (!this.hasPendingAllocations) {
            this.toast.warning("Aucune allocation à enregistrer");
            return;
        }
        if (this.isOverflow) {
            this.toast.error("Le total alloué dépasse le montant de l'encaissement");
            return;
        }

        this.state.saving = true;
        let okCount = 0;
        let errors = [];

        try {
            for (const [factureIdStr, montant] of Object.entries(this.state.allocations)) {
                const m = Number(montant);
                if (!m || m <= 0) continue;
                try {
                    await this.orm.call(
                        "recouvrement.encaissement",
                        "appliquer_lettrage",
                        [this.state.encaissement.id, Number(factureIdStr), m],
                    );
                    okCount += 1;
                } catch (err) {
                    const f = this.state.factures.find(
                        (x) => x.id === Number(factureIdStr),
                    );
                    errors.push(`${f?.name || factureIdStr}: ${err?.message?.message || err?.message || "erreur"}`);
                }
            }

            if (okCount > 0) {
                this.toast.success(
                    `${okCount} lettrage(s) enregistré(s)`,
                    {
                        description: errors.length
                            ? `${errors.length} erreur(s) — voir détails`
                            : "Encaissement mis à jour.",
                    },
                );
            }
            if (errors.length) {
                this.toast.error(
                    "Certaines allocations ont échoué",
                    { description: errors.slice(0, 2).join(" · "), duration: 9000 },
                );
            }

            // Recharger les données depuis le serveur
            await this.loadData();
        } finally {
            this.state.saving = false;
        }
    }

    onBack() {
        this.actionService.doAction(
            "recouvrement_contentieux.action_recouvrement_encaissement",
        );
    }

    /* -----------------------------------------------------------------
     *  Helpers
     * ----------------------------------------------------------------- */
    fmt(n) {
        return new Intl.NumberFormat("fr-FR", {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        }).format(Number(n) || 0);
    }

    fmtDate(s) {
        if (!s) return "-";
        const d = new Date(s);
        if (isNaN(d.getTime())) return s;
        return new Intl.DateTimeFormat("fr-FR").format(d);
    }

    statutLabel(code) {
        return {
            normal: "Normal",
            precontentieux: "Précontentieux",
            contentieux: "Contentieux",
            bloque_juridique: "Bloqué",
            bloque_technique: "Blocage technique",
            recouvre: "Recouvré",
        }[code] || code;
    }
}

registry
    .category("actions")
    .add(
        "recouvrement_contentieux.encaissement_lettrage_page",
        EncaissementLettragePage,
    );
