/** @odoo-module **/

import { Component } from "@odoo/owl";

/**
 * CidDrawer — Panneau latéral réutilisable
 *
 * Usage :
 *   <CidDrawer isOpen="state.drawerOpen"
 *              title="'Titre du drawer'"
 *              onClose="() => this.closeDrawer()">
 *
 *     <t t-set-slot="header-extra">
 *       <!-- badges, actions dans le header (optionnel) -->
 *     </t>
 *
 *     <t t-set-slot="default">
 *       <!-- Corps libre — sections, formulaires, listes -->
 *     </t>
 *
 *     <t t-set-slot="footer">
 *       <!-- Boutons d'action principaux (optionnel) -->
 *     </t>
 *
 *   </CidDrawer>
 *
 * Props :
 *   isOpen   {Boolean}  Contrôle la visibilité
 *   title    {String}   Titre affiché dans le header
 *   subtitle {String}   Sous-titre optionnel
 *   size     {String}   'sm' | 'md' (défaut) | 'lg'
 *   onClose  {Function} Callback fermeture (clic overlay ou bouton ✕)
 */
export class CidDrawer extends Component {
    static template = "recouvrement_contentieux.CidDrawer";
    static props = {
        isOpen:   { type: Boolean },
        title:    { type: String, optional: true },
        subtitle: { type: String, optional: true },
        size:     { type: String, optional: true },   // sm | md | lg
        onClose:  { type: Function, optional: true },
        slots:    { type: Object, optional: true },
    };
    static defaultProps = { size: "md", title: "" };

    get panelClass() {
        return `cid-drawer__panel cid-drawer__panel--${this.props.size || "md"}`;
    }

    onOverlayClick() {
        if (this.props.onClose) this.props.onClose();
    }

    onCloseClick() {
        if (this.props.onClose) this.props.onClose();
    }
}

/**
 * CidDrawerSection — Section titrée dans un drawer
 *
 * <CidDrawerSection title="'Informations client'" icon="'fa-user'">
 *   ...contenu...
 * </CidDrawerSection>
 */
export class CidDrawerSection extends Component {
    static template = "recouvrement_contentieux.CidDrawerSection";
    static props = {
        title: { type: String, optional: true },
        icon:  { type: String, optional: true },
        slots: { type: Object, optional: true },
    };
}

/**
 * CidDrawerInfoRow — Ligne label/valeur dans un drawer
 *
 * <CidDrawerInfoRow icon="'fa-envelope-o'" label="'Email'"
 *                   value="client.email"
 *                   href="'mailto:' + client.email"/>
 */
export class CidDrawerInfoRow extends Component {
    static template = "recouvrement_contentieux.CidDrawerInfoRow";
    static props = {
        icon:  { type: String, optional: true },
        label: { type: String, optional: true },
        value: { type: String, optional: true },
        href:  { type: String, optional: true },
    };
}
