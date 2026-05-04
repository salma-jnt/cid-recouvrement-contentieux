/** @odoo-module **/

import { Component, useState } from "@odoo/owl";

/**
 * <CidSearchBar placeholder="'Rechercher…'" value="state.query" onSearch.bind="onSearch"/>
 *
 * Props :
 *   placeholder  – texte grisé (défaut : "Rechercher…")
 *   value        – valeur initiale / contrôlée de l'extérieur
 *   onSearch(q)  – callback appelé après 350 ms de silence
 */
export class CidSearchBar extends Component {
    static template = "recouvrement_contentieux.CidSearchBar";
    static props = {
        placeholder: { type: String, optional: true },
        value:       { type: String, optional: true },
        onSearch:    { type: Function, optional: true },
    };
    static defaultProps = { placeholder: "Rechercher…", value: "" };

    setup() {
        this.state = useState({ query: this.props.value || "" });
        this._timer = null;
    }

    onInput(ev) {
        this.state.query = ev.target.value;
        clearTimeout(this._timer);
        this._timer = setTimeout(() => this.props.onSearch?.(this.state.query), 350);
    }

    onClear() {
        this.state.query = "";
        clearTimeout(this._timer);
        this.props.onSearch?.("");
    }
}
