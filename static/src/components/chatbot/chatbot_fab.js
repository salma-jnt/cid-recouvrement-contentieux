/** @odoo-module **/

import { Component, useState, useRef, onMounted } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { rpc } from "@web/core/network/rpc";

/**
 * Chatbot flottant CID
 * - Bouton FAB en bas à droite, visible partout
 * - Click → panneau coulissant avec input NLQ
 * - Backend : POST /recouvrement/chat (à brancher en Phase 5 sur LangChain)
 *
 * Pour l'instant le backend renvoie une réponse stub indiquant que
 * la pile NLQ sera branchée en Phase 5.
 */
export class CidChatbotFab extends Component {
    static template = "recouvrement_contentieux.CidChatbotFab";
    static props = {};

    setup() {
        this.toast = useService("cid_toast");
        this.state = useState({
            open: false,
            input: "",
            sending: false,
            messages: [
                {
                    id: 1,
                    role: "assistant",
                    content:
                        "Bonjour 👋 Je suis l'assistant de recouvrement CID. " +
                        "Posez-moi des questions en langage naturel sur vos factures, " +
                        "encaissements ou dossiers. Exemples : « combien de factures " +
                        "non soldées du client X ? », « total encaissé ce mois-ci ? »",
                },
            ],
        });
        this.scrollRef = useRef("scrollArea");
    }

    toggle() {
        this.state.open = !this.state.open;
        if (this.state.open) {
            // re-render then scroll
            setTimeout(() => this._scrollToBottom(), 60);
        }
    }

    onInputKey(ev) {
        if (ev.key === "Enter" && !ev.shiftKey) {
            ev.preventDefault();
            this.send();
        }
    }

    async send() {
        const text = (this.state.input || "").trim();
        if (!text || this.state.sending) return;

        // Push user message
        const userMsg = {
            id: Date.now(),
            role: "user",
            content: text,
        };
        this.state.messages.push(userMsg);
        this.state.input = "";
        this.state.sending = true;
        this._scrollToBottom();

        try {
            const reply = await rpc("/recouvrement/chat", {
                question: text,
                context: { /* ex: filtres en cours, pôle, période */ },
            });
            this.state.messages.push({
                id: Date.now() + 1,
                role: "assistant",
                content: reply.answer || "Désolé, je n'ai pas pu obtenir de réponse.",
                data: reply.data || null,
            });
        } catch (err) {
            this.state.messages.push({
                id: Date.now() + 1,
                role: "assistant",
                error: true,
                content:
                    "Une erreur est survenue. Le backend NLQ sera branché en " +
                    "Phase 5 (LangChain + Anthropic).",
            });
        } finally {
            this.state.sending = false;
            this._scrollToBottom();
        }
    }

    _scrollToBottom() {
        const el = this.scrollRef.el;
        if (el) {
            requestAnimationFrame(() => {
                el.scrollTop = el.scrollHeight;
            });
        }
    }

    suggestionClick(text) {
        this.state.input = text;
    }
}

// Mount globally
registry.category("main_components").add("CidChatbotFab", {
    Component: CidChatbotFab,
});
