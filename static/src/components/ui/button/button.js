/** @odoo-module **/

import { Component } from "@odoo/owl";

/**
 * <CidButton variant="primary|secondary|ghost|danger|accent"
 *            size="sm|md|lg"
 *            icon="fa-plus"
 *            iconPosition="left|right"
 *            loading="false"
 *            disabled="false"
 *            onClick="...">
 *   Label
 * </CidButton>
 */
export class CidButton extends Component {
    static template = "recouvrement_contentieux.CidButton";
    static props = {
        variant:      { type: String, optional: true },
        size:         { type: String, optional: true },
        icon:         { type: String, optional: true },
        iconPosition: { type: String, optional: true },
        loading:      { type: Boolean, optional: true },
        disabled:     { type: Boolean, optional: true },
        type:         { type: String, optional: true },
        onClick:      { type: Function, optional: true },
        block:        { type: Boolean, optional: true },
        slots:        { type: Object, optional: true },
    };
    static defaultProps = {
        variant: "primary",
        size: "md",
        iconPosition: "left",
        loading: false,
        disabled: false,
        type: "button",
        block: false,
    };

    get classes() {
        const cls = [
            "cid-btn",
            `cid-btn--${this.props.variant}`,
            `cid-btn--${this.props.size}`,
        ];
        if (this.props.block) cls.push("cid-btn--block");
        if (this.props.loading) cls.push("cid-btn--loading");
        return cls.join(" ");
    }

    onClick(ev) {
        if (this.props.disabled || this.props.loading) {
            ev.preventDefault();
            return;
        }
        if (this.props.onClick) this.props.onClick(ev);
    }
}
