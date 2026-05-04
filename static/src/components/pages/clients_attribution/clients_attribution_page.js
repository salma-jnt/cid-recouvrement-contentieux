/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

import { CidButton }    from "../../ui/button/button";
import { CidDataTable } from "../../ui/data_table/data_table";
import { CidSearchBar } from "../../ui/search_bar/search_bar";

export class ClientsAttributionPage extends Component {
    static template = "recouvrement_contentieux.ClientsAttributionPage";
    static components = { CidButton, CidDataTable, CidSearchBar };
    static props = { "*": true };

    setup() {
        this.orm   = useService("orm");
        this.toast = useService("cid_toast");

        this.state = useState({
            loading:  true,
            rows:     [],
            total:    0,
            page:     1,
            pageSize: 25,
            search:   "",
            saving:   false,
        });

        this.clientTypes      = [];
        this.assignmentMap    = new Map();   // partner_id → assignment record
        this.clientPartnerIds = [];          // IDs distincts depuis recouvrement.facture

        onWillStart(() => this.loadAll());
    }

    // ── Colonnes ─────────────────────────────────────────────────────────────
    get columns() {
        return [
            { key: "name",             label: "Client",             sortable: true, minWidth: "200px" },
            { key: "email",            label: "Email",              minWidth: "200px" },
            { key: "phone",            label: "Téléphone",          minWidth: "140px" },
            { key: "current_type_id",  label: "Type de client",     minWidth: "240px", render: "type_select" },
            { key: "date_attribution", label: "Date d'attribution", minWidth: "150px", render: "date_cell" },
        ];
    }

    // ── Chargement initial (types + assignments + IDs clients) ────────────────
    async loadAll() {
        this.state.loading = true;
        try {
            const [types, assignments, clientGroups] = await Promise.all([
                this.orm.searchRead(
                    "recouvrement.client.type",
                    [],
                    ["id", "name"],
                    { order: "name asc" },
                ),
                this.orm.searchRead(
                    "recouvrement.client.assignment",
                    [],
                    ["id", "partner_id", "client_type_id", "date_attribution"],
                ),
                // Récupère les client_id distincts (GROUP BY côté serveur)
                this.orm.readGroup(
                    "recouvrement.facture",
                    [],
                    ["client_id"],
                    ["client_id"],
                ),
            ]);

            this.clientTypes = types;
            this.assignmentMap = new Map(
                assignments.map(a => [a.partner_id[0], a]),
            );

            // Extrait les IDs depuis le résultat du readGroup
            this.clientPartnerIds = clientGroups
                .map(g => Array.isArray(g.client_id) ? g.client_id[0] : null)
                .filter(Boolean);

            await this._loadPartners();
        } catch (err) {
            this.toast.error("Erreur de chargement", { description: err?.message || "" });
            this.state.loading = false;
        }
    }

    async _loadPartners() {
        this.state.loading = true;
        try {
            const domain = this._buildDomain();
            const offset = (this.state.page - 1) * this.state.pageSize;

            const [partners, total] = await Promise.all([
                this.orm.searchRead(
                    "res.partner",
                    domain,
                    ["id", "name", "email", "phone"],
                    { limit: this.state.pageSize, offset, order: "name asc" },
                ),
                this.orm.searchCount("res.partner", domain),
            ]);

            this.state.rows = partners.map(p => {
                const a = this.assignmentMap.get(p.id);
                return {
                    id:               p.id,
                    name:             p.name || "—",
                    email:            p.email || "",
                    phone:            p.phone || "",
                    current_type_id:  a ? a.client_type_id[0] : null,
                    assignment_id:    a ? a.id : null,
                    date_attribution: a ? a.date_attribution : null,
                };
            });
            this.state.total = total;
        } finally {
            this.state.loading = false;
        }
    }

    _buildDomain() {
        // Base : uniquement les partenaires référencés dans les factures de recouvrement
        const domain = this.clientPartnerIds.length
            ? [["id", "in", this.clientPartnerIds]]
            : [["id", "=", -1]];   // aucune facture importée → liste vide

        const q = this.state.search.trim();
        if (q) {
            domain.push("|", "|",
                ["name", "ilike", q],
                ["email", "ilike", q],
                ["phone", "ilike", q],
            );
        }
        return domain;
    }

    // ── Handlers pagination / recherche ──────────────────────────────────────
    onPageChange(page)     { this.state.page = page; this._loadPartners(); }
    onPageSizeChange(size) { this.state.pageSize = size; this.state.page = 1; this._loadPartners(); }
    onSearch(query)        { this.state.search = query; this.state.page = 1; this._loadPartners(); }

    // ── Attribution inline ────────────────────────────────────────────────────
    async onTypeChange(row, ev) {
        const typeIdStr = ev.target.value;
        const typeId    = typeIdStr ? parseInt(typeIdStr, 10) : false;

        this.state.saving = true;
        try {
            if (typeId) {
                if (row.assignment_id) {
                    await this.orm.write(
                        "recouvrement.client.assignment",
                        [row.assignment_id],
                        { client_type_id: typeId },
                    );
                    const a = this.assignmentMap.get(row.id);
                    if (a) { a.client_type_id = [typeId, ""]; }
                } else {
                    const [newId] = await this.orm.create(
                        "recouvrement.client.assignment",
                        [{ partner_id: row.id, client_type_id: typeId }],
                    );
                    const today = new Date().toISOString().slice(0, 10);
                    this.assignmentMap.set(row.id, {
                        id: newId,
                        partner_id:    [row.id, row.name],
                        client_type_id:[typeId, ""],
                        date_attribution: today,
                    });
                }
            } else if (row.assignment_id) {
                await this.orm.unlink(
                    "recouvrement.client.assignment",
                    [row.assignment_id],
                );
                this.assignmentMap.delete(row.id);
            }

            this.toast.success("Attribution enregistrée");
            await this._loadPartners();
        } catch (err) {
            this.toast.error("Erreur", { description: err?.message || "" });
            await this._loadPartners();
        } finally {
            this.state.saving = false;
        }
    }

    // ── Helpers ──────────────────────────────────────────────────────────────
    fmtDate(v) {
        if (!v) { return "—"; }
        return new Intl.DateTimeFormat("fr-FR").format(new Date(v));
    }
}

registry.category("actions").add(
    "recouvrement_contentieux.clients_attribution_page",
    ClientsAttributionPage,
);
