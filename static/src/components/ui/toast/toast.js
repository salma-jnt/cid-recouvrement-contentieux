/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

/**
 * <CidToastContainer/> — monté une fois dans le main_components_registry.
 *
 * CORRECTION CRITIQUE : on enveloppe this.toast.state dans useState().
 * Sans useState(), OWL monte le composant une fois mais ne le re-rend
 * JAMAIS quand les toasts changent, même si le service utilise reactive().
 * useState() est le seul mécanisme qui abonne un composant OWL au re-rendu
 * lors des mutations d'un objet réactif externe.
 */
export class CidToastContainer extends Component {
    static template = "recouvrement_contentieux.CidToastContainer";
    static props = {};

    setup() {
        const toastService = useService("cid_toast");
        // ✅ useState() sur l'objet reactive() du service
        // → OWL subscribe ce composant : toute mutation de state.toasts
        //   déclenche un re-rendu automatique
        this.state = useState(toastService.state);
        this.toast = toastService;
    }

    onClose(id) {
        this.toast.dismiss(id);
    }

    onActionClick(t) {
        if (t.onAction) t.onAction();
        this.toast.dismiss(t.id);
    }

    iconFor(variant) {
        return {
            success: "fa-check-circle",
            error:   "fa-times-circle",
            warning: "fa-exclamation-triangle",
            info:    "fa-info-circle",
        }[variant] || "fa-info-circle";
    }
}

registry.category("main_components").add("CidToastContainer", {
    Component: CidToastContainer,
});