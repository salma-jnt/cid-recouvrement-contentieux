/** @odoo-module **/

import { Component } from "@odoo/owl";

/**
 * <CidCard padded="true" elevated="false" interactive="false">
 *   <t t-set-slot="header"> ... </t>
 *   <t t-set-slot="default"> ... </t>
 *   <t t-set-slot="footer"> ... </t>
 * </CidCard>
 */
export class CidCard extends Component {
    static template = "recouvrement_contentieux.CidCard";
    static props = {
        padded:      { type: Boolean, optional: true },
        elevated:    { type: Boolean, optional: true },
        interactive: { type: Boolean, optional: true },
        accentBar:   { type: String, optional: true }, // primary|accent|success|warning|danger|mauve
        slots:       { type: Object, optional: true },
        onClick:     { type: Function, optional: true },
    };
    static defaultProps = { padded: true, elevated: false, interactive: false };

    get classes() {
        const cls = ["cid-card"];
        if (this.props.padded) cls.push("cid-card--padded");
        if (this.props.elevated) cls.push("cid-card--elevated");
        if (this.props.interactive) cls.push("cid-card--interactive");
        if (this.props.accentBar) cls.push(`cid-card--accent-${this.props.accentBar}`);
        return cls.join(" ");
    }

    onClick(ev) {
        if (this.props.onClick) this.props.onClick(ev);
    }
}
