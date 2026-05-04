/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

import { CidButton }    from "../../ui/button/button";
import { CidBadge }     from "../../ui/badge/badge";
import { CidSkeleton }  from "../../ui/skeleton/skeleton";
import { CidDataTable } from "../../ui/data_table/data_table";

/**
 * EncaissementsListPage — liste OWL des encaissements
 *
 * Remplace la vue list Odoo standard (ir.actions.act_window).
 * Utilise CidDataTable pour le rendu, tri, pagination.
 * Clic sur une ligne → EncaissementDetailPage.
 */
export class EncaissementsListPage extends Component {
    static template = "recouvrement_contentieux.EncaissementsListPage";
    static components = { CidButton, CidBadge, CidSkeleton, CidDataTable };
    static props = { "*": true };

    setup() {
        this.orm           = useService("orm");
        this.actionService = useService("action");
        this.toast         = useService("cid_toast");

        this.state = useState({
            loading: true,
            rows:    [],
            total:   0,
            page:    1,
            pageSize: 20,
            sortColumn: "date_operation",
            sortDir:    "desc",
            filter:     "all",   // all | pending | solde
        });

        onWillStart(() => this.loadData());
    }

    // ── Colonnes ─────────────────────────────────────────────────────────────
    get columns() {
        return [
            { key: "name",           label: "Référence",         sortable: true,  minWidth: "140px" },
            { key: "date_operation", label: "Date d'opération",  sortable: true,  minWidth: "130px",
              format: v => v ? new Intl.DateTimeFormat("fr-FR").format(new Date(v)) : "—" },
            { key: "client_name",    label: "Client",            sortable: true,  minWidth: "160px" },
            { key: "code_affaire",   label: "Code d'affaire",    minWidth: "140px" },
            { key: "mode_paiement",  label: "Mode de paiement",  minWidth: "130px",
              format: v => ({ virement: "Virement", cheque: "Chèque", espece: "Espèces",
                              lcn: "LCN", traite: "Traite" }[v] || v || "—") },
            { key: "montant",        label: "Montant",           align: "right",  sortable: true,  minWidth: "120px",
              format: v => v != null ? new Intl.NumberFormat("fr-FR", { minimumFractionDigits: 2 }).format(v) : "—" },
            { key: "montant_alloue", label: "Montant alloué",    align: "right",  minWidth: "130px",
              format: v => v != null ? new Intl.NumberFormat("fr-FR", { minimumFractionDigits: 2 }).format(v) : "—" },
            { key: "reste_a_allouer",label: "Reste à allouer",   align: "right",  minWidth: "130px",
              format: v => v != null ? new Intl.NumberFormat("fr-FR", { minimumFractionDigits: 2 }).format(v) : "—" },
            { key: "etat_lettrage",  label: "État du lettrage",  minWidth: "140px", render: "etat_badge" },
        ];
    }

    // ── Chargement ───────────────────────────────────────────────────────────
    async loadData() {
        this.state.loading = true;
        try {
            const domain = this._buildDomain();
            const order  = `${this.state.sortColumn} ${this.state.sortDir}`;
            const offset = (this.state.page - 1) * this.state.pageSize;

            const [records, total] = await Promise.all([
                this.orm.searchRead(
                    "recouvrement.encaissement",
                    domain,
                    ["id", "name", "date_operation", "client_id", "code_affaire",
                     "mode_paiement", "montant", "montant_alloue", "reste_a_allouer",
                     "etat_lettrage", "currency_id"],
                    { limit: this.state.pageSize, offset, order },
                ),
                this.orm.searchCount("recouvrement.encaissement", domain),
            ]);

            this.state.rows = records.map(r => ({
                ...r,
                client_name: r.client_id?.[1] || "—",
                currency:    r.currency_id?.[1] || "MAD",
            }));
            this.state.total = total;
        } catch (err) {
            this.toast.error("Erreur de chargement", { description: err?.message || "" });
        } finally {
            this.state.loading = false;
        }
    }

    _buildDomain() {
        const base = [];
        if (this.state.filter === "pending") base.push(["reste_a_allouer", ">", 0]);
        if (this.state.filter === "solde")   base.push(["etat_lettrage", "=", "solde"]);
        return base;
    }

    // ── Handlers ─────────────────────────────────────────────────────────────
    onSort({ column, dir }) {
        this.state.sortColumn = column;
        this.state.sortDir    = dir;
        this.state.page       = 1;
        this.loadData();
    }

    onPageChange(page) {
        this.state.page = page;
        this.loadData();
    }

    onPageSizeChange(size) {
        this.state.pageSize = size;
        this.state.page     = 1;
        this.loadData();
    }

    onRowClick(row) {
        this.actionService.doAction({
            type:    "ir.actions.client",
            tag:     "recouvrement_contentieux.encaissement_detail_page",
            name:    row.name || "Encaissement",
            context: { encaissement_id: row.id },
            target:  "current",
        });
    }

    onFilterChange(filter) {
        this.state.filter = filter;
        this.state.page   = 1;
        this.loadData();
    }

    onNew() {
        this.actionService.doAction({
            type:       "ir.actions.act_window",
            res_model:  "recouvrement.encaissement",
            views:      [[false, "form"]],
            target:     "current",
        });
    }

    // ── Helpers UI ───────────────────────────────────────────────────────────
    etatLabel(etat) {
        return { en_cours: "En cours", solde: "Soldé", en_attente: "En attente" }[etat] || etat || "—";
    }

    etatVariant(etat) {
        return { en_cours: "warning", solde: "success", en_attente: "neutral" }[etat] || "neutral";
    }
}

registry.category("actions").add(
    "recouvrement_contentieux.encaissements_list_page",
    EncaissementsListPage,
);
