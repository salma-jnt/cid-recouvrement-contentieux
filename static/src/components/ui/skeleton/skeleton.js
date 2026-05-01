/** @odoo-module **/

import { Component } from "@odoo/owl";

/**
 * <CidSkeleton width="100%" height="20px" rounded="md" lines="3"/>
 *
 * Placeholders animés pendant le chargement.
 */
export class CidSkeleton extends Component {
    static template = "recouvrement_contentieux.CidSkeleton";
    static props = {
        width:   { type: String, optional: true },
        height:  { type: String, optional: true },
        rounded: { type: String, optional: true },
        lines:   { type: Number, optional: true },
        circle:  { type: Boolean, optional: true },
    };
    static defaultProps = {
        width: "100%",
        height: "16px",
        rounded: "md",
        lines: 1,
        circle: false,
    };

    get style() {
        return `width:${this.props.width};height:${this.props.height};`;
    }

    get classes() {
        const cls = ["cid-skel"];
        if (this.props.circle) cls.push("cid-skel--circle");
        else cls.push(`cid-skel--rounded-${this.props.rounded}`);
        return cls.join(" ");
    }

    get range() {
        return Array.from({ length: this.props.lines }, (_, i) => i);
    }
}
