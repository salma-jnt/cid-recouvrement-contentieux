/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

import { CidButton }    from "../../ui/button/button";
import { CidBadge }     from "../../ui/badge/badge";
import { CidDataTable } from "../../ui/data_table/data_table";
import { CidSearchBar } from "../../ui/search_bar/search_bar";

export class DossiersListPage extends Component {
    static template = "recouvrement_contentieux.DossiersListPage";
    static components = { CidButton, CidBadge, CidDataTable, CidSearchBar };
    static props = { "*": true };

    setup() {
        this.orm           = useService("orm");
        this.actionService = useService("action");
        this.toast         = useService("cid_toast");

        this.state = useState({
            loading:    true,
            rows:       [],
            total:      0,
            page:       1,
            pageSize:   20,
            sortColumn: "name",
            sortDir:    "asc",
            filter:     "all",
            search:     "",
        });

        onWillStart(() => this.loadData());
    }

    // ── Colonnes — identiques à la vue liste Odoo ────────────────────────────
    get columns() {
        const fmtMoney = v => v != null
            ? new Intl.NumberFormat("fr-FR", { minimumFractionDigits: 2 }).format(v)
            : "—";
        const fmtDate = v => v
            ? new Intl.DateTimeFormat("fr-FR").format(new Date(v))
            : "—";
        const fmtM2o = v => Array.isArray(v) ? v[1] : (v || "—");

        return [
            { key: "name",              label: "Référence",          sortable: true,  minWidth: "140px" },
            { key: "procedure_id",      label: "Procédure",          minWidth: "160px", format: fmtM2o },
            { key: "phase_courante",    label: "Phase courante",     minWidth: "150px", format: v => v || "—" },
            { key: "date_depot_groupe", label: "Date de dépôt",      sortable: true,  minWidth: "120px", format: fmtDate },
            { key: "nombre_factures",   label: "Factures",           align: "center", minWidth: "80px" },
            { key: "nombre_clients",    label: "Clients",            align: "center", minWidth: "80px" },
            { key: "montant_ttc",       label: "Montant TTC",        align: "right",  sortable: true, minWidth: "130px", format: fmtMoney },
            { key: "montant_encaisse",  label: "Montant encaissé",   align: "right",  sortable: true, minWidth: "140px", format: fmtMoney },
            { key: "reste_a_recouvrer", label: "Reste à recouvrer",  align: "right",  sortable: true, minWidth: "140px", format: fmtMoney },
            { key: "prochaine_echeance",label: "Prochaine échéance", sortable: true,  minWidth: "140px", format: fmtDate },
            { key: "state",             label: "Statut",             minWidth: "120px", render: "state_badge" },
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
                    "recouvrement.recouvrement",
                    domain,
                    ["id", "name", "procedure_id", "phase_courante", "date_depot_groupe",
                     "nombre_factures", "nombre_clients", "montant_ttc", "montant_encaisse",
                     "reste_a_recouvrer", "prochaine_echeance", "state"],
                    { limit: this.state.pageSize, offset, order },
                ),
                this.orm.searchCount("recouvrement.recouvrement", domain),
            ]);

            this.state.rows  = records;
            this.state.total = total;
        } catch (err) {
            this.toast.error("Erreur de chargement", { description: err?.message || "" });
        } finally {
            this.state.loading = false;
        }
    }

    _buildDomain() {
        const domain = [];
        switch (this.state.filter) {
            case "ouverts":   domain.push(["state", "in",  ["ouvert", "en_cours", "en_retard"]]); break;
            case "en_retard": domain.push(["state", "=",   "en_retard"]); break;
            case "bloque":    domain.push(["state", "=",   "bloque"]);    break;
            case "solde":     domain.push(["state", "=",   "solde"]);     break;
        }
        const q = this.state.search.trim();
        if (q) {
            domain.push("|", "|",
                ["name", "ilike", q],
                ["procedure_id.name", "ilike", q],
                ["phase_courante", "ilike", q],
            );
        }
        return domain;
    }

    // ── Handlers ─────────────────────────────────────────────────────────────
    onSort({ column, dir }) {
        this.state.sortColumn = column;
        this.state.sortDir    = dir;
        this.state.page       = 1;
        this.loadData();
    }

    onPageChange(page)     { this.state.page = page; this.loadData(); }
    onPageSizeChange(size) { this.state.pageSize = size; this.state.page = 1; this.loadData(); }
    onFilterChange(filter) { this.state.filter = filter; this.state.page = 1; this.loadData(); }
    onSearch(query)        { this.state.search = query; this.state.page = 1; this.loadData(); }

    onRowClick(row) {
        this.actionService.doAction({
            type:    "ir.actions.client",
            tag:     "recouvrement_contentieux.dossier_detail_page",
            name:    row.name || "Dossier",
            context: { dossier_id: row.id },
            target:  "current",
        });
    }

    // ── Helpers UI ───────────────────────────────────────────────────────────
    stateLabel(state) {
        return {
            ouvert:    "Ouvert",
            en_cours:  "En cours",
            en_retard: "En retard",
            bloque:    "Bloqué",
            solde:     "Soldé",
        }[state] || state || "—";
    }

    stateVariant(state) {
        return {
            ouvert:    "warning",
            en_cours:  "warning",
            en_retard: "danger",
            bloque:    "danger",
            solde:     "success",
        }[state] || "neutral";
    }
}

registry.category("actions").add(
    "recouvrement_contentieux.dossiers_list_page",
    DossiersListPage,
);
