import json
import logging
from datetime import date, timedelta

from odoo import http, _
from odoo.http import request

_logger = logging.getLogger(__name__)

MAX_LIMIT = 100


# ---------------------------------------------------------------------
# Détection LangChain
# ---------------------------------------------------------------------
try:
    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain_core.tools import tool
    from langchain_core.messages import HumanMessage, SystemMessage

    # LangGraph 1.x: create_react_agent lives in langgraph.prebuilt.
    # The deprecation warning pointing to langchain.agents is misleading
    # (that import does not exist). Suppress the warning and use it directly.
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        from langgraph.prebuilt import create_react_agent

    LANGCHAIN_AVAILABLE = True
    _logger.info("✅ LangChain/LangGraph imports OK")
except ImportError as e:
    LANGCHAIN_AVAILABLE = False
    _logger.warning(f"⚠️ LangChain not available: {e}")


# =====================================================================
# CONTROLLER
# =====================================================================
class RecouvrementChatbotController(http.Controller):

    @http.route(
        '/recouvrement/chat',
        type='json',
        auth='user',
        methods=['POST'],
        csrf=False,
    )
    def chat(self, question=None, context=None, **kwargs):

        if not question or not isinstance(question, str):
            return {
                'answer': _("Veuillez poser une question."),
                'data': None,
                'meta': {'error': 'no_question'},
            }

        # 🔐 récupération clé
        api_key = request.env['ir.config_parameter'].sudo().get_param(
            'cid_gemini_api_key'
        )

        _logger.warning("=== DEBUG CHATBOT ===")
        _logger.warning(f"API KEY = {'SET' if api_key else 'MISSING'}")
        _logger.warning(f"LANGCHAIN_AVAILABLE = {LANGCHAIN_AVAILABLE}")

        if not api_key:
            _logger.error("❌ Gemini API key manquante")
            return {
                'answer': "Clé Gemini non configurée.",
                'data': None,
                'meta': {'error': 'no_api_key'},
            }

        if not LANGCHAIN_AVAILABLE:
            _logger.error("❌ LangChain non disponible")
            return self._chat_stub(question, fallback_reason="langchain_not_installed")

        # 🚀 MODE AGENT
        try:
            _logger.warning("🚀 USING GEMINI AGENT")
            return self._chat_with_agent(question, context, api_key)
        except Exception as e:
            _logger.exception("❌ Agent error → fallback stub")
            return self._chat_stub(question, fallback_reason=str(e))

    # ------------------------------------------------------------------
    # AGENT MODE  (LangGraph create_react_agent — LangChain 1.x compatible)
    # ------------------------------------------------------------------
    def _chat_with_agent(self, question, context, api_key):

        env = request.env
        tools = self._build_tools(env)

        llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash",
            google_api_key=api_key,
            temperature=0,
        )

        system_prompt = (
            "Tu es un assistant spécialisé dans le recouvrement de créances. "
            "Réponds en français. Utilise les outils disponibles pour répondre "
            "avec des données précises. Si aucun outil ne correspond, réponds "
            "de manière générale."
        )

        if tools:
            # Mode agent avec outils
            agent = create_react_agent(llm, tools)
            result = agent.invoke({
                "messages": [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=question),
                ]
            })
            # Le dernier message est la réponse finale de l'agent
            last_message = result["messages"][-1]
            answer = last_message.content
        else:
            # Mode LLM simple sans outils
            response = llm.invoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=question),
            ])
            answer = response.content

        return {
            'answer': answer,
            'data': None,
            'meta': {'mode': 'agent' if tools else 'llm_simple'},
        }

    # ------------------------------------------------------------------
    # TOOLS
    # ------------------------------------------------------------------
    def _build_tools(self, env):

        @tool
        def count_factures_non_soldees(client_name: str = "") -> dict:
            """Compte les factures non soldées (reste à payer > 0).
            Peut filtrer par nom de client."""
            domain = [('reste_a_payer', '>', 0)]
            if client_name:
                domain.append(('client_id.name', 'ilike', client_name))

            recs = env['recouvrement.facture'].search(domain, limit=MAX_LIMIT)

            return {
                'count': len(recs),
                'total': round(sum(recs.mapped('reste_a_payer')), 2),
            }

        @tool
        def total_encaisse(period: str = "all") -> dict:
            """Retourne le total encaissé pour une période donnée.
            Valeurs possibles pour period : all, today, week, month, year."""
            today = date.today()
            domain = []

            if period == 'today':
                domain = [('date_operation', '=', today.isoformat())]
            elif period == 'week':
                domain = [('date_operation', '>=', (today - timedelta(days=7)).isoformat())]
            elif period == 'month':
                domain = [('date_operation', '>=', today.replace(day=1).isoformat())]
            elif period == 'year':
                domain = [('date_operation', '>=', today.replace(month=1, day=1).isoformat())]

            recs = env['recouvrement.encaissement'].search(domain, limit=MAX_LIMIT)

            return {
                'count': len(recs),
                'total': round(sum(recs.mapped('montant')), 2),
            }

        @tool
        def top_clients_a_recouvrer(limit: int = 5) -> list:
            """Retourne les clients avec le plus grand montant restant à payer."""
            partners = env['res.partner'].search([('customer_rank', '>', 0)])

            result = []

            for p in partners:
                factures = env['recouvrement.facture'].search([
                    ('client_id', '=', p.id),
                    ('reste_a_payer', '>', 0),
                ], limit=MAX_LIMIT)

                if factures:
                    result.append({
                        'name': p.display_name,
                        'reste': round(sum(factures.mapped('reste_a_payer')), 2),
                    })

            result.sort(key=lambda x: x['reste'], reverse=True)

            return result[:limit]

        return [
            count_factures_non_soldees,
            total_encaisse,
            top_clients_a_recouvrer,
        ]

    # ------------------------------------------------------------------
    # STUB MODE (fallback sans LLM)
    # ------------------------------------------------------------------
    def _chat_stub(self, question, fallback_reason=None):

        q = question.lower()
        env = request.env

        if 'impayé' in q or 'reste' in q:
            recs = env['recouvrement.facture'].search([
                ('reste_a_payer', '>', 0),
            ], limit=MAX_LIMIT)
            total = sum(recs.mapped('reste_a_payer'))
            return {
                'answer': f"{len(recs)} factures non soldées, total {total:,.2f} DH",
                'data': None,
                'meta': {'mode': 'stub'},
            }

        if 'encaissé' in q:
            recs = env['recouvrement.encaissement'].search([], limit=MAX_LIMIT)
            total = sum(recs.mapped('montant'))
            return {
                'answer': f"Total encaissé : {total:,.2f} DH",
                'data': None,
                'meta': {'mode': 'stub'},
            }

        return {
            'answer': "Je ne peux pas répondre précisément en mode basique.",
            'data': None,
            'meta': {'mode': 'stub', 'fallback': True, 'reason': fallback_reason},
        }
