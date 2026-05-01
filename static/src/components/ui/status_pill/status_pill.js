/** @odoo-module **/

import { Component } from "@odoo/owl";

/**
 * <CidStatusPill color="vert|orange|rouge|mauve" withDot="true">Label</CidStatusPill>
 *
 * Composant dédié aux statuts visuels du cahier de charge :
 *   - vert   : phase normale, suivi régulier
 *   - orange : blocage technique
 *   - rouge  : alerte / précontentieux / contentieux
 *   - mauve  : phase de relance importante
 */
export class CidStatusPill extends Component {
    static template = "recouvrement_contentieux.CidStatusPill";
    static props = {
        color:   { type: String, optional: true },
        withDot: { type: Boolean, optional: true },
        size:    { type: String, optional: true },
        slots:   { type: Object, optional: true },
    };
    static defaultProps = { color: "vert", withDot: true, size: "sm" };

    get classes() {
        return [
            "cid-status-pill",
            `cid-status-pill--${this.props.color}`,
            `cid-status-pill--${this.props.size}`,
        ].join(" ");
    }

    get colorLabels() {
        return {
            vert: "Normal",
            orange: "Blocage technique",
            rouge: "Alerte",
            mauve: "Relance",
        };
    }
}
