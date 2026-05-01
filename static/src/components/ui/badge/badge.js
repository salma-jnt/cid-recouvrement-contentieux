/** @odoo-module **/

import { Component } from "@odoo/owl";

/**
 * <CidBadge variant="primary|accent|success|warning|danger|info|neutral|mauve"
 *           subtle="false"
 *           size="sm|md"
 *           icon="fa-check">
 *   Label
 * </CidBadge>
 */
export class CidBadge extends Component {
    static template = "recouvrement_contentieux.CidBadge";
    static props = {
        variant: { type: String, optional: true },
        subtle:  { type: Boolean, optional: true },
        size:    { type: String, optional: true },
        icon:    { type: String, optional: true },
        slots:   { type: Object, optional: true },
    };
    static defaultProps = { variant: "neutral", subtle: false, size: "sm" };

    get classes() {
        return [
            "cid-badge",
            `cid-badge--${this.props.variant}`,
            `cid-badge--${this.props.size}`,
            this.props.subtle ? "cid-badge--subtle" : "cid-badge--solid",
        ].join(" ");
    }
}
