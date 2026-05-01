/** @odoo-module **/

import { Component } from "@odoo/owl";

/**
 * <CidStepper steps="state.phases" currentIndex="state.current"
 *             orientation="horizontal|vertical"/>
 *
 * Chaque step :
 *   { id, label, status: 'done'|'current'|'pending'|'reporte', color: 'vert'|'orange'|'rouge'|'mauve', date, subtitle }
 *
 * Utilisation principale : afficher l'enchaînement des phases d'une procédure
 * dans un dossier de recouvrement, avec couleurs CID + indicateur visuel
 * de la phase courante.
 */
export class CidStepper extends Component {
    static template = "recouvrement_contentieux.CidStepper";
    static props = {
        steps:        { type: Array },
        currentIndex: { type: Number, optional: true },
        orientation:  { type: String, optional: true },
        compact:      { type: Boolean, optional: true },
        onStepClick:  { type: Function, optional: true },
    };
    static defaultProps = {
        currentIndex: 0,
        orientation: "horizontal",
        compact: false,
    };

    classFor(step, idx) {
        const cls = ["cid-stepper__step"];
        cls.push(`cid-stepper__step--${step.status || "pending"}`);
        if (step.color) cls.push(`cid-stepper__step--color-${step.color}`);
        if (idx === this.props.currentIndex) cls.push("cid-stepper__step--active");
        if (this.props.onStepClick) cls.push("cid-stepper__step--clickable");
        return cls.join(" ");
    }

    iconFor(step) {
        if (step.status === "done") return "fa-check";
        if (step.status === "reporte") return "fa-clock-o";
        if (step.status === "current") return "fa-circle";
        return "";
    }

    onStepClick(step, idx) {
        if (this.props.onStepClick) this.props.onStepClick(step, idx);
    }

    get wrapperClass() {
        const cls = ["cid-stepper", `cid-stepper--${this.props.orientation}`];
        if (this.props.compact) cls.push("cid-stepper--compact");
        return cls.join(" ");
    }
}
