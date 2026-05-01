/** @odoo-module **/

import { reactive } from "@odoo/owl";
import { registry } from "@web/core/registry";

/**
 * Service Toast global — accessible via useService("cid_toast").
 *
 * Usage :
 *   const toast = useService("cid_toast");
 *   toast.success("Importation réussie", { description: "42 factures créées." });
 *   toast.error("Échec de l'envoi");
 *   toast.warning("Attention", { description: "Le délai est dépassé." });
 *   toast.info("Information", { duration: 8000 });
 */
export const cidToastService = {
    start() {
        const state = reactive({ toasts: [] });
        let nextId = 1;

        const remove = (id) => {
            const idx = state.toasts.findIndex((t) => t.id === id);
            if (idx >= 0) {
                state.toasts.splice(idx, 1);
            }
        };

        const push = (variant, title, opts = {}) => {
            const id = nextId++;
            const toast = {
                id,
                variant, // 'success' | 'error' | 'warning' | 'info'
                title,
                description: opts.description || "",
                duration: opts.duration ?? 4500,
                actionLabel: opts.actionLabel || null,
                onAction: opts.onAction || null,
            };
            state.toasts.push(toast);
            if (toast.duration > 0) {
                setTimeout(() => remove(id), toast.duration);
            }
            return id;
        };

        return {
            state,
            success: (title, opts) => push("success", title, opts),
            error:   (title, opts) => push("error", title, opts),
            warning: (title, opts) => push("warning", title, opts),
            info:    (title, opts) => push("info", title, opts),
            dismiss: remove,
        };
    },
};

registry.category("services").add("cid_toast", cidToastService);
