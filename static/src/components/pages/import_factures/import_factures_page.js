/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

import { CidButton } from "../../ui/button/button";
import { CidCard } from "../../ui/card/card";
import { CidDropzone } from "../../ui/dropzone/dropzone";
import { CidBadge } from "../../ui/badge/badge";

/**
 * Page moderne « Importer des factures »
 *
 * Remplace le wizard Odoo standard par une page OWL plein écran avec :
 *   - Zone de dropzone luxe
 *   - Sélecteur de mois d'upload (cahier de charge — marquage analytique)
 *   - Aperçu du fichier sélectionné
 *   - Bouton « Importer » avec spinner
 *   - Affichage du résumé après import (créées / mises à jour / verrouillées)
 *   - Toast success/error global
 */
export class ImportFacturesPage extends Component {
    static template = "recouvrement_contentieux.ImportFacturesPage";
    static components = { CidButton, CidCard, CidDropzone, CidBadge };
    static props = { "*": true };

    setup() {
        this.orm = useService("orm");
        this.toast = useService("cid_toast");
        this.actionService = useService("action");

        this.state = useState({
            files: [],
            moisUpload: this._currentYearMonth(),
            importing: false,
            result: null,  // {created, updated, locked, errors, total}
        });
    }

    _currentYearMonth() {
        const d = new Date();
        return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
    }

    onFilesChanged(files) {
        this.state.files = files;
        this.state.result = null;
    }

    onMoisChange(ev) {
        this.state.moisUpload = ev.target.value;
    }

    canImport() {
        return this.state.files.length > 0
            && this.state.moisUpload
            && !this.state.importing;
    }

    async onImport() {
        if (!this.canImport()) return;
        this.state.importing = true;
        this.state.result = null;

        try {
            const file = this.state.files[0];
            const base64 = await this._fileToBase64(file);

            // Appel ORM de la méthode wizard (qu'on appellera directement
            // sans passer par l'UI wizard). En Phase 4 on fera une méthode
            // RPC dédiée plus propre.
            const wizardId = await this.orm.create(
                "recouvrement.facture.import.wizard",
                [{
                    file_data: base64,
                    file_name: file.name,
                    mois_upload: this.state.moisUpload,
                }],
            );

            const result = await this.orm.call(
                "recouvrement.facture.import.wizard",
                "action_import",
                [wizardId],
                { context: { from_owl_page: true } },
            );

            // Le wizard retourne directement {created, updated, locked, total, errors}
            // quand from_owl_page=true dans le context
            const summary = {
                created: result?.created ?? 0,
                updated: result?.updated ?? 0,
                locked:  result?.locked  ?? 0,
                total:   result?.total   ?? 0,
                errors:  result?.errors  ?? [],
            };

            console.log("✅ [DEBUG] Résultat de l'ORM :", result);
            console.log("✅ [DEBUG] Résumé formaté :", summary);

            // On affiche le toast EN PREMIER (avant de mettre à jour le state)
            // Ainsi, si le template XML plante à cause de this.state.result, le toast sera quand même affiché !
            this.toast.success(
                "Importation réussie",
                {
                    description: `${summary.created || 0} créée(s), ${summary.updated || 0} mise(s) à jour.`,
                },
            );
            console.log("✅ [DEBUG] Toast success appelé avec succès");

            // On met à jour l'affichage de la page ensuite
            this.state.result = summary;
        } catch (err) {
            console.error("❌ [DEBUG] Erreur attrapée :", err);
            this.toast.error(
                "Échec de l'importation",
                {
                    description: err?.message?.message || err?.message || "Erreur inconnue.",
                    duration: 8000,
                },
            );
        } finally {
            this.state.importing = false;
        }
    }

    _fileToBase64(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => {
                const result = reader.result;
                const base64 = result.includes(",") ? result.split(",")[1] : result;
                resolve(base64);
            };
            reader.onerror = reject;
            reader.readAsDataURL(file);
        });
    }

    onReset() {
        this.state.files = [];
        this.state.result = null;
    }

    onSeeFactures() {
        this.actionService.doAction(
            "recouvrement_contentieux.action_recouvrement_facture",
        );
    }
}

registry
    .category("actions")
    .add("recouvrement_contentieux.import_factures_page", ImportFacturesPage);
