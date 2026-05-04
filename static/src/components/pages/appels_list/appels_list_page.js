/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

import { CidButton }    from "../../ui/button/button";
import { CidBadge }     from "../../ui/badge/badge";
import { CidDataTable } from "../../ui/data_table/data_table";
import { CidSearchBar } from "../../ui/search_bar/search_bar";

export class AppelsListPage extends Component {
    static template = "recouvrement_contentieux.AppelsListPage";
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
            sortColumn: "mandatory_date",
            sortDir:    "asc",
            filter:     "todo",   // todo | reporte | done | en_retard | all
            search:     "",
        });

        onWillStart(() => this.loadData());
    }

    // ── Colonnes ─────────────────────────────────────────────────────────────
    get columns() {
        const fmtDate = v => v
            ? new Intl.DateTimeFormat("fr-FR").format(new Date(v))
            : "—";
        const fmtM2o  = v => Array.isArray(v) ? v[1] : (v || "—");

        return [
            { key: "name",           label: "Intitulé",         sortable: true, minWidth: "180px" },
            { key: "recouvrement_id",label: "Dossier",          minWidth: "150px", format: fmtM2o },
            { key: "client_id",      label: "Client",           minWidth: "150px", format: fmtM2o },
            { key: "responsible_id", label: "Responsable",      minWidth: "140px", format: fmtM2o },
            { key: "mandatory_date", label: "Échéance",         sortable: true,  minWidth: "120px", format: fmtDate },
            { key: "action_prise",   label: "Issue",            minWidth: "150px", render: "action_prise_badge" },
            { key: "state",          label: "Statut",           minWidth: "110px", render: "state_badge" },
            { key: "is_overdue",     label: "En retard",        minWidth: "100px", render: "overdue_badge" },
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
                    "recouvrement.action",
                    domain,
                    ["id", "name", "recouvrement_id", "client_id", "responsible_id",
                     "mandatory_date", "date_done", "state", "is_overdue", "action_prise"],
                    { limit: this.state.pageSize, offset, order },
                ),
                this.orm.searchCount("recouvrement.action", domain),
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
        const domain = [["action_type", "=", "appel"]];

        switch (this.state.filter) {
            case "todo":      domain.push(["state", "=", "todo"]);   break;
            case "reporte":   domain.push(["state", "=", "reporte"]); break;
            case "done":      domain.push(["state", "=", "done"]);   break;
            case "en_retard": domain.push(["is_overdue", "=", true], ["state", "in", ["todo", "reporte"]]); break;
        }

        const q = this.state.search.trim();
        if (q) {
            domain.push("|", "|",
                ["name", "ilike", q],
                ["client_id.name", "ilike", q],
                ["recouvrement_id.name", "ilike", q],
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
            tag:     "recouvrement_contentieux.action_execution_page",
            name:    row.name || "Appel",
            context: { action_id: row.id },
            target:  "current",
        });
    }

    // ── Labels & variantes ───────────────────────────────────────────────────
    stateLabel(state) {
        return { todo: "À faire", done: "Réalisée", reporte: "Reportée", cancel: "Annulée" }[state] || state || "—";
    }
    stateVariant(state) {
        return { todo: "info", done: "success", reporte: "warning", cancel: "neutral" }[state] || "neutral";
    }

    actionPriseLabel(v) {
        return {
            aucune:        "—",
            paiement:      "Promesse de paiement",
            plan_paiement: "Plan de paiement",
            dialogue:      "Dialogue établi",
            non_joignable: "Non joignable",
            litige:        "Litige déclaré",
            escalade:      "Escalade",
        }[v] || v || "—";
    }
    actionPriseVariant(v) {
        return {
            aucune:        "neutral",
            paiement:      "success",
            plan_paiement: "success",
            dialogue:      "info",
            non_joignable: "warning",
            litige:        "danger",
            escalade:      "danger",
        }[v] || "neutral";
    }
}

registry.category("actions").add(
    "recouvrement_contentieux.appels_list_page",
    AppelsListPage,
);
