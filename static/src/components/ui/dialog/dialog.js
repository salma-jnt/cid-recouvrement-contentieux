/** @odoo-module **/

import { Component, useEffect } from "@odoo/owl";
import { CidButton } from "../button/button";

/**
 * <CidDialog open="state.open" title="Confirmer"
 *            size="sm|md|lg|xl"
 *            onClose.bind="...">
 *   <t t-set-slot="default"> body content </t>
 *   <t t-set-slot="footer">
 *     <CidButton variant="'secondary'" onClick="...">Annuler</CidButton>
 *     <CidButton variant="'primary'" onClick="...">Confirmer</CidButton>
 *   </t>
 * </CidDialog>
 */
export class CidDialog extends Component {
    static template = "recouvrement_contentieux.CidDialog";
    static components = { CidButton };
    static props = {
        open:           { type: Boolean },
        title:          { type: String, optional: true },
        description:    { type: String, optional: true },
        size:           { type: String, optional: true },
        closeOnOverlay: { type: Boolean, optional: true },
        onClose:        { type: Function, optional: true },
        slots:          { type: Object, optional: true },
    };
    static defaultProps = {
        size: "md",
        closeOnOverlay: true,
        title: "",
        description: "",
    };

    setup() {
        useEffect(
            () => {
                const onKey = (ev) => {
                    if (ev.key === "Escape" && this.props.open && this.props.onClose) {
                        this.props.onClose();
                    }
                };
                document.addEventListener("keydown", onKey);
                return () => document.removeEventListener("keydown", onKey);
            },
            () => [this.props.open],
        );
    }

    onOverlayClick() {
        if (this.props.closeOnOverlay && this.props.onClose) {
            this.props.onClose();
        }
    }

    onCloseClick() {
        if (this.props.onClose) this.props.onClose();
    }
}
