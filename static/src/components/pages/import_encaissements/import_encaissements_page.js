/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

import { CidButton } from "../../ui/button/button";
import { CidCard } from "../../ui/card/card";
import { CidDropzone } from "../../ui/dropzone/dropzone";
import { CidBadge } from "../../ui/badge/badge";

export class ImportEncaissementsPage extends Component {
    static template = "recouvrement_contentieux.ImportEncaissementsPage";

    static components = {
        CidButton,
        CidCard,
        CidDropzone,
        CidBadge,
    };

    setup() {
        this.actionService = useService("action");
        this.toast = useService("cid_toast");

        // ✅ ÉTAT obligatoire
        this.state = useState({
            files: [],
            moisImport: "",
            importing: false,
            result: null,
        });
    }

    // ===============================
    // Actions UI
    // ===============================

    onBack() {
        this.actionService.doAction(
            "recouvrement_contentieux.action_recouvrement_encaissement"
        );
    }

    onFilesChanged(files) {
        this.state.files = files;
    }

    onMoisChange(ev) {
        this.state.moisImport = ev.target.value;
    }

    onReset() {
        this.state.files = [];
        this.state.moisImport = "";
        this.state.result = null;
    }

    canImport() {
        return this.state.files.length > 0 && this.state.moisImport;
    }

    async onImport() {
        this.state.importing = true;

        try {
            // ⚠️ Simulation (à remplacer par RPC plus tard)
            await new Promise((resolve) => setTimeout(resolve, 1000));

            this.state.result = {
                created: 10,
                updated: 5,
                ignored: 2,
                total: 17,
            };
            
            // Afficher le toast de succès
            this.toast.success("Importation terminée avec succès !");
        } catch (e) {
            console.error(e);
            // Afficher le toast d'erreur en cas de problème
            this.toast.error("Erreur lors de l'importation", { description: e.message || "Erreur inconnue" });
        } finally {
            this.state.importing = false;
        }
    }
}

registry.category("actions").add(
    "recouvrement_contentieux.import_encaissements_page",
    ImportEncaissementsPage
);