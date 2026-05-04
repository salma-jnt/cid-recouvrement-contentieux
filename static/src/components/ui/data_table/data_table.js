/** @odoo-module **/

import { Component, useState, useRef } from "@odoo/owl";
import { CidPagination } from "../pagination/pagination";
import { CidSkeleton } from "../skeleton/skeleton";
import { CidEmptyState } from "../empty_state/empty_state";

/**
 * CidDataTable — composant tableau générique inspiré de shadcn/ui DataTable
 *
 * Usage minimal :
 * ───────────────
 * <CidDataTable
 *     columns="tableColumns"
 *     rows="tableRows"
 *     loading="state.loading"
 * />
 *
 * Usage complet :
 * ───────────────
 * <CidDataTable
 *     columns="tableColumns"
 *     rows="tableRows"
 *     loading="state.loading"
 *     rowKey="'id'"
 *     selectable="true"
 *     sortable="true"
 *     sortColumn="state.sortCol"
 *     sortDir="state.sortDir"
 *     paginated="true"
 *     page="state.page"
 *     pageSize="state.pageSize"
 *     total="state.total"
 *     stickyHeader="true"
 *     striped="true"
 *     compact="false"
 *     emptyIcon="'fa-table'"
 *     emptyTitle="'Aucune donnée'"
 *     emptyDescription="'Aucun enregistrement trouvé.'"
 *     onSort.bind="onSort"
 *     onRowClick.bind="onRowClick"
 *     onSelectionChange.bind="onSelectionChange"
 *     onPageChange.bind="onPageChange"
 *     onPageSizeChange.bind="onPageSizeChange"
 * />
 *
 * Colonnes (columns) — tableau de définitions :
 * ─────────────────────────────────────────────
 * [
 *   {
 *     key: "name",           // clé dans la ligne (obligatoire)
 *     label: "Nom",          // en-tête affiché
 *     sortable: true,        // colonne triable (optionnel)
 *     align: "left",         // "left" | "center" | "right"  (défaut: left)
 *     width: "200px",        // largeur fixe (optionnel)
 *     minWidth: "120px",     // min-width (optionnel)
 *     className: "...",      // classe CSS sur les cellules (optionnel)
 *     format: (val, row) => String,  // formateur de valeur (optionnel)
 *     render: "template_name",       // nom d'un slot de rendu (optionnel)
 *   },
 *   ...
 * ]
 *
 * Lignes (rows) — tableau d'objets :
 * ───────────────────────────────────
 * Chaque objet doit avoir la propriété définie par `rowKey` (défaut: "id").
 */
export class CidDataTable extends Component {
    static template = "recouvrement_contentieux.CidDataTable";
    static components = { CidPagination, CidSkeleton, CidEmptyState };

    static props = {
        // Données
        columns:           { type: Array },
        rows:              { type: Array },
        loading:           { type: Boolean, optional: true },

        // Clé unique de chaque ligne (prop name dans la row)
        rowKey:            { type: String, optional: true },

        // Sélection
        selectable:        { type: Boolean, optional: true },

        // Tri
        sortable:          { type: Boolean, optional: true },   // active le tri globalement
        sortColumn:        { type: String, optional: true },    // colonne courante triée
        sortDir:           { type: String, optional: true },    // "asc" | "desc"

        // Pagination (contrôlée de l'extérieur)
        paginated:         { type: Boolean, optional: true },
        page:              { type: Number, optional: true },
        pageSize:          { type: Number, optional: true },
        total:             { type: Number, optional: true },
        pageSizeOptions:   { type: Array, optional: true },

        // Apparence
        stickyHeader:      { type: Boolean, optional: true },
        striped:           { type: Boolean, optional: true },
        compact:           { type: Boolean, optional: true },
        bordered:          { type: Boolean, optional: true },
        hoverable:         { type: Boolean, optional: true },

        // État vide
        emptyIcon:         { type: String, optional: true },
        emptyTitle:        { type: String, optional: true },
        emptyDescription:  { type: String, optional: true },

        // Callbacks
        onSort:            { type: Function, optional: true },
        onRowClick:        { type: Function, optional: true },
        onSelectionChange: { type: Function, optional: true },
        onPageChange:      { type: Function, optional: true },
        onPageSizeChange:  { type: Function, optional: true },

        // Slots
        slots:             { type: Object, optional: true },
    };

    static defaultProps = {
        loading: false,
        rowKey: "id",
        selectable: false,
        sortable: false,
        sortColumn: null,
        sortDir: "asc",
        paginated: false,
        page: 1,
        pageSize: 20,
        total: 0,
        pageSizeOptions: [10, 20, 50, 100],
        stickyHeader: true,
        striped: false,
        compact: false,
        bordered: false,
        hoverable: true,
        emptyIcon: "fa-table",
        emptyTitle: "Aucune donnée",
        emptyDescription: "Aucun enregistrement à afficher.",
    };

    setup() {
        this.selection = useState({ keys: new Set() });
    }

    // ─── Computed ────────────────────────────────────────────────────────────

    get tableClasses() {
        return [
            "cid-dt",
            this.props.striped    ? "cid-dt--striped"    : "",
            this.props.compact    ? "cid-dt--compact"    : "",
            this.props.bordered   ? "cid-dt--bordered"   : "",
            this.props.hoverable  ? "cid-dt--hoverable"  : "",
            this.props.stickyHeader ? "cid-dt--sticky-header" : "",
            this.props.onRowClick ? "cid-dt--clickable"  : "",
        ].filter(Boolean).join(" ");
    }

    get isEmpty() {
        return !this.props.loading && this.props.rows.length === 0;
    }

    get allSelected() {
        if (!this.props.rows.length) return false;
        return this.props.rows.every(row =>
            this.selection.keys.has(this._key(row))
        );
    }

    get someSelected() {
        return this.selection.keys.size > 0 && !this.allSelected;
    }

    get selectedRows() {
        return this.props.rows.filter(row =>
            this.selection.keys.has(this._key(row))
        );
    }

    get skeletonRows() {
        return Array.from({ length: this.props.pageSize || 5 });
    }

    // ─── Helpers ─────────────────────────────────────────────────────────────

    _key(row) {
        return row[this.props.rowKey];
    }

    cellValue(row, col) {
        const val = row[col.key];
        if (typeof col.format === "function") return col.format(val, row);
        return val ?? "—";
    }

    colHeaderClass(col) {
        return [
            "cid-dt__th",
            col.align  ? `cid-dt__th--${col.align}` : "cid-dt__th--left",
            (this.props.sortable || col.sortable) && col.key
                ? "cid-dt__th--sortable" : "",
            this.props.sortColumn === col.key ? "cid-dt__th--sorted" : "",
        ].filter(Boolean).join(" ");
    }

    colCellClass(col) {
        return [
            "cid-dt__td",
            col.align ? `cid-dt__td--${col.align}` : "cid-dt__td--left",
            col.className || "",
        ].filter(Boolean).join(" ");
    }

    colStyle(col) {
        const parts = [];
        if (col.width) parts.push(`width:${col.width}`);
        if (col.minWidth) parts.push(`min-width:${col.minWidth}`);
        return parts.join(";") || undefined;
    }

    sortIcon(col) {
        if (this.props.sortColumn !== col.key) return "fa-sort";
        return this.props.sortDir === "asc" ? "fa-sort-asc" : "fa-sort-desc";
    }

    isSelected(row) {
        return this.selection.keys.has(this._key(row));
    }

    // ─── Handlers ────────────────────────────────────────────────────────────

    onHeaderClick(col) {
        if ((!this.props.sortable && !col.sortable) || !col.key) return;
        if (!this.props.onSort) return;

        const dir = this.props.sortColumn === col.key && this.props.sortDir === "asc"
            ? "desc" : "asc";
        this.props.onSort({ column: col.key, dir });
    }

    onRowClick(row, ev) {
        if (!this.props.onRowClick) return;
        // Ne pas déclencher si on clique sur la case à cocher
        if (ev.target.closest(".cid-dt__checkbox")) return;
        this.props.onRowClick(row, ev);
    }

    toggleRow(row) {
        const key = this._key(row);
        if (this.selection.keys.has(key)) {
            this.selection.keys.delete(key);
        } else {
            this.selection.keys.add(key);
        }
        this._emitSelection();
    }

    toggleAll() {
        if (this.allSelected) {
            this.selection.keys.clear();
        } else {
            this.props.rows.forEach(row => this.selection.keys.add(this._key(row)));
        }
        this._emitSelection();
    }

    _emitSelection() {
        if (this.props.onSelectionChange) {
            this.props.onSelectionChange(this.selectedRows);
        }
    }

    onPageChange(page) {
        if (this.props.onPageChange) this.props.onPageChange(page);
    }

    onPageSizeChange(size) {
        if (this.props.onPageSizeChange) this.props.onPageSizeChange(size);
    }
}