/** @odoo-module **/

import { Component } from "@odoo/owl";
import { CidButton } from "../button/button";

/**
 * <CidEmptyState icon="fa-inbox" title="Aucune facture"
 *                description="Importez votre premier fichier pour commencer."
 *                actionLabel="Importer" onAction.bind="..."/>
 */
export class CidEmptyState extends Component {
    static template = "recouvrement_contentieux.CidEmptyState";
    static components = { CidButton };
    static props = {
        icon:        { type: String, optional: true },
        title:       { type: String },
        description: { type: String, optional: true },
        actionLabel: { type: String, optional: true },
        onAction:    { type: Function, optional: true },
        slots:       { type: Object, optional: true },
    };
    static defaultProps = { icon: "fa-inbox" };
}
