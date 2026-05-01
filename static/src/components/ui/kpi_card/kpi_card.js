/** @odoo-module **/

import { Component } from "@odoo/owl";

/**
 * <CidKpiCard label="Reste à recouvrer" value="1 234 567 DH"
 *             icon="fa-money" trend="+5.2%" trendDirection="up|down|flat"
 *             accent="primary|accent|success|warning|danger|mauve"
 *             onClick="..."/>
 */
export class CidKpiCard extends Component {
    static template = "recouvrement_contentieux.CidKpiCard";
    static props = {
        label:          { type: String },
        value:          { type: [String, Number] },
        subtitle:       { type: String, optional: true },
        icon:           { type: String, optional: true },
        trend:          { type: String, optional: true },
        trendDirection: { type: String, optional: true },
        accent:         { type: String, optional: true },
        onClick:        { type: Function, optional: true },
        loading:        { type: Boolean, optional: true },
    };
    static defaultProps = { accent: "primary", trendDirection: "flat", loading: false };

    get classes() {
        const cls = ["cid-kpi", `cid-kpi--${this.props.accent}`];
        if (this.props.onClick) cls.push("cid-kpi--clickable");
        return cls.join(" ");
    }

    get trendIcon() {
        return {
            up: "fa-arrow-up",
            down: "fa-arrow-down",
            flat: "fa-minus",
        }[this.props.trendDirection];
    }

    onClick() {
        if (this.props.onClick) this.props.onClick();
    }
}
