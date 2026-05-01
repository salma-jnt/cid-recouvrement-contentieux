/** @odoo-module **/

import { Component, useState, useRef } from "@odoo/owl";

/**
 * <CidDropzone accept=".xlsx,.xls"
 *              multiple="false"
 *              maxSizeMB="10"
 *              files="state.files"
 *              onFilesChanged.bind="...">
 *   Glissez votre fichier ici
 * </CidDropzone>
 *
 * - Drag & drop
 * - Click to browse
 * - Preview avec icône, nom, taille
 * - Bouton de suppression par fichier
 * - Validation taille / type côté client
 */
export class CidDropzone extends Component {
    static template = "recouvrement_contentieux.CidDropzone";
    static props = {
        accept:          { type: String, optional: true },
        multiple:        { type: Boolean, optional: true },
        maxSizeMB:       { type: Number, optional: true },
        files:           { type: Array, optional: true },
        onFilesChanged:  { type: Function, optional: true },
        title:           { type: String, optional: true },
        subtitle:        { type: String, optional: true },
    };
    static defaultProps = {
        accept: "",
        multiple: false,
        maxSizeMB: 25,
        files: [],
        title: "Glissez votre fichier ici",
        subtitle: "ou cliquez pour parcourir",
    };

    setup() {
        this.state = useState({ dragOver: false, error: null });
        this.inputRef = useRef("input");
    }

    onClick() {
        this.inputRef.el?.click();
    }

    onInputChange(ev) {
        this._handleFiles(ev.target.files);
        ev.target.value = ""; // permet de re-sélectionner le même fichier
    }

    onDragOver(ev) {
        ev.preventDefault();
        this.state.dragOver = true;
    }
    onDragLeave(ev) {
        ev.preventDefault();
        this.state.dragOver = false;
    }
    onDrop(ev) {
        ev.preventDefault();
        this.state.dragOver = false;
        this._handleFiles(ev.dataTransfer.files);
    }

    _handleFiles(fileList) {
        this.state.error = null;
        const incoming = Array.from(fileList || []);
        if (!incoming.length) return;

        // Validation taille
        const maxBytes = this.props.maxSizeMB * 1024 * 1024;
        const tooBig = incoming.find((f) => f.size > maxBytes);
        if (tooBig) {
            this.state.error = `Le fichier "${tooBig.name}" dépasse ${this.props.maxSizeMB} Mo.`;
            return;
        }

        // Validation type (basique, sur l'extension)
        if (this.props.accept) {
            const exts = this.props.accept.split(",").map((s) => s.trim().toLowerCase());
            const bad = incoming.find(
                (f) => !exts.some((e) => f.name.toLowerCase().endsWith(e.replace(/^\./, "."))),
            );
            if (bad) {
                this.state.error = `Type de fichier non accepté : "${bad.name}". Attendu : ${this.props.accept}.`;
                return;
            }
        }

        const newFiles = this.props.multiple
            ? [...(this.props.files || []), ...incoming]
            : incoming.slice(0, 1);

        if (this.props.onFilesChanged) {
            this.props.onFilesChanged(newFiles);
        }
    }

    onRemove(index, ev) {
        ev.stopPropagation();
        const next = [...this.props.files];
        next.splice(index, 1);
        if (this.props.onFilesChanged) this.props.onFilesChanged(next);
    }

    formatSize(bytes) {
        if (bytes < 1024) return `${bytes} o`;
        if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} Ko`;
        return `${(bytes / (1024 * 1024)).toFixed(2)} Mo`;
    }

    iconFor(file) {
        const name = (file.name || "").toLowerCase();
        if (name.endsWith(".xlsx") || name.endsWith(".xls") || name.endsWith(".csv")) return "fa-file-excel-o";
        if (name.endsWith(".pdf")) return "fa-file-pdf-o";
        return "fa-file-o";
    }
}
