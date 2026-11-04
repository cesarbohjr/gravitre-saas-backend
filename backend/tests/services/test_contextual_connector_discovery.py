"""Offline contracts for inventory routing, live evidence and dialogue repair."""
import ast
import importlib.util
import sys
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app.services.connector_discovery_context import connector_inventory_intent
from app.services.clarification_repair import repair_generic_clarification


class ContextContracts(unittest.TestCase):
    def test_inventory_variants_and_followups(self):
        for question in ["What other email connectors do I have?", "No, I meant what other email connectors do I have?", "Sorry, I meant what other email provider can you use?", "K. What other email connectors do I have?", "Which email accounts are connected?", "List my email integrations.", "What other email provider can you use?", "Which other email services can Gravitre access?"]:
            with self.subTest(question=question):
                self.assertEqual(connector_inventory_intent(question).category, "email")
        history = [{"role": "user", "content": "What other email connectors do I have?"}, {"role": "assistant", "content": "I may be missing context — could you clarify or point me to a specific record or document?"}]
        for followup in ["Do I not have others?", "Which ones?", "Any others?", "Anything else?", "What other emails do I have?", "Okay. I asked asked what other Gmails... what other emails do I have?"]:
            self.assertEqual(connector_inventory_intent(followup, history).category, "email")

    def test_context_does_not_cross_topic_or_authorize_actions(self):
        history = [{"role": "user", "content": "What email connectors do I have?"}, {"role": "user", "content": "Let's pick something else."}]
        self.assertIsNone(connector_inventory_intent("Do I not have others?", history))
        for text in ["No, I meant send this message", "What other emails do I have?", "Do I not have others?", "Which accounts do I have?", "Send it", "What email connectors do I have and send Sarah a message?", "Delete my email accounts"]:
            self.assertIsNone(connector_inventory_intent(text))

    def test_continued_followups_preserve_category(self):
        history = [{"role": "user", "content": "What email connectors do I have?"}, {"role": "user", "content": "Which ones?"}]
        self.assertEqual(connector_inventory_intent("Do I not have others?", history).category, "email")


class InventoryEvidenceContracts(unittest.TestCase):
    def setUp(self):
        # Only presentation/import infrastructure is stubbed. The status service,
        # parser, semantic registry and capability registry run their real source.
        grace = types.ModuleType("app.capability_ontology.conversational_grace")
        grace.vendor_display_label = lambda slug: str(slug).replace("_", " ").title()
        self.imports = patch.dict(sys.modules, {grace.__name__: grace})
        self.imports.start()
        path = Path(__file__).resolve().parents[2] / "app/services/connector_status_reply_service.py"
        spec = importlib.util.spec_from_file_location("_cq_status_under_test", path)
        self.service = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = self.service
        spec.loader.exec_module(self.service)
        self.addCleanup(sys.modules.pop, spec.name, None)
        self.addCleanup(self.imports.stop)

    def answer(self, rows, *, question="What other email connectors do I have?", history=None, error=False):
        with patch.object(self.service, "_rows_from_get_connector_status", return_value=(rows, error)) as read, patch.object(self.service, "_allowed_vendors", return_value=frozenset({"gmail", "microsoft365", "sendgrid"})):
            result = self.service.answer_connector_status_question(question, client=object(), org_id="org-a", settings=object(), environment_name="acceptance", conversation_history=history)
            if result is not None:
                self.assertEqual(read.call_args.kwargs["org_id"], "org-a")
                self.assertEqual(read.call_args.kwargs["environment_name"], "acceptance")
            return result

    def test_live_microsoft_inventory_and_followup_exclude_unrelated_crm(self):
        rows = [{"vendor": "microsoft365", "execution_available": True}, {"vendor": "hubspot", "execution_available": True}]
        history = [{"role": "user", "content": "What email connectors do I have?"}]
        result = self.answer(rows, question="Do I not have others?", history=history)
        self.assertIn("Microsoft 365 (Outlook) is connected", result.text)
        self.assertIn("one configured email service", result.text)
        self.assertIn("catalog options, not additional connected accounts", result.text)
        self.assertNotIn("Hubspot", result.text)
        self.assertIn("permissions still need checking", result.text)
        self.assertEqual(result.source, "getConnectorStatus")

    def test_exact_provider_question_after_gmail_discussion_respects_live_status(self):
        rows = [
            {"vendor": "gmail", "execution_available": True},
            {"vendor": "microsoft365", "execution_available": False, "blocking_reason": "missing_scope"},
        ]
        history = [
            {"role": "user", "content": "Can you find an email through Gmail?"},
            {"role": "assistant", "content": "Gmail is configured."},
        ]
        result = self.answer(
            rows,
            question="What other email provider can you use?",
            history=history,
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.source, "getConnectorStatus")
        self.assertIn("Microsoft 365 (Outlook) is configured but needs additional permissions", result.text)
        self.assertIn("Gmail is connected", result.text)
        self.assertIn("permissions still need checking", result.text)
        self.assertNotIn("Microsoft 365 (Outlook) is connected", result.text)

    def test_provider_question_status_failure_never_claims_outlook(self):
        result = self.answer(None, question="What other email provider can you use?", error=True)
        self.assertEqual(result.source, "unverified")
        self.assertIn("couldn't verify", result.text)
        self.assertNotIn("Outlook is connected", result.text)

    def test_missing_scopes_and_expired_auth_remain_visible(self):
        for row, expected in [({"vendor": "microsoft365", "blocking_reason": "missing_scope"}, "needs additional permissions"), ({"vendor": "gmail", "auth_status": "auth_expired"}, "needs reconnection")]:
            result = self.answer([row])
            self.assertIn(expected, result.text)
            self.assertNotIn("didn't find", result.text)

    def test_empty_inventory_offers_supported_catalog_without_claiming_connected(self):
        result = self.answer([])
        self.assertIn("didn't find a configured email connector", result.text)
        self.assertIn("Supported email options", result.text)
        self.assertIn("Microsoft 365", result.text)

    def test_failed_live_read_does_not_claim_absence_or_catalog_results(self):
        result = self.answer(None, error=True)
        self.assertEqual(result.source, "unverified")
        self.assertIn("couldn't verify", result.text)
        self.assertNotIn("Supported", result.text)


class ClarificationContracts(unittest.TestCase):
    generic = "I may be missing context — could you clarify or point me to a specific record or document?"

    def test_useful_answer_is_not_polluted_by_generic_suffix(self):
        answer = "Your connector needs reconnection."
        self.assertEqual(repair_generic_clarification(answer + "\n\n" + self.generic, query="Check my connector", history=[], needs_clarification=True), answer)
        self.assertEqual(repair_generic_clarification(answer, query="Check my connector", history=[], needs_clarification=True), answer)

    def test_empty_generic_and_validation_fallback_get_specific_questions(self):
        for answer in ["", self.generic, "I found related information, but not enough reliable context to answer confidently. Could you clarify what you need or point me to a specific document or record?"]:
            result = repair_generic_clarification(answer, query="What other emails do I have?", history=[], needs_clarification=True)
            self.assertIn("connected email services or individual messages", result)
            self.assertNotIn("missing context", result)
            self.assertIn("couldn't verify", result)

    def test_explicit_connector_question_not_reframed_as_ambiguous_email(self):
        for query in [
            "What other email connectors do I have?",
            "Which email providers are connected?",
            "Show my integrations",
        ]:
            with self.subTest(query=query):
                answer = repair_generic_clarification(
                    self.generic, query=query, history=[], needs_clarification=True,
                )
                self.assertIn("couldn't verify your connected email services", answer)
                self.assertIn("retry the connector-status check", answer)
                self.assertNotIn("individual messages", answer)

    def test_repeated_question_changes_strategy_and_specific_questions_are_preserved(self):
        prior = repair_generic_clarification(self.generic, query="Find that record", history=[], needs_clarification=True)
        result = repair_generic_clarification(self.generic, query="Find that record", history=[{"role": "assistant", "content": prior}], needs_clarification=True)
        self.assertNotEqual(prior, result)
        self.assertIn("naming the service or record", result)
        answer = "Which HubSpot company do you mean?"
        self.assertEqual(repair_generic_clarification(answer, query="Find it", history=[], needs_clarification=True), answer)


class GatewayContracts(unittest.IsolatedAsyncioTestCase):
    async def test_followup_cannot_reuse_context_free_cache(self):
        path = Path(__file__).resolve().parents[2] / "app/services/intent_gateway.py"
        source = ast.parse(path.read_text())
        node = next(n for n in source.body if isinstance(n, ast.FunctionDef) and n.name == "response_cache_eligible")
        # An AST-extracted function has no module globals unless supplied.
        # Supply the real regex module and an inert operator-task classifier;
        # the cases here are all informational cache exclusions.
        import re
        namespace = {"re": re, "is_operator_task_shaped": lambda _text: False}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])), str(path), "exec"), namespace)
        service = types.ModuleType("app.services.conversational_execution_service")
        import re
        service.CONFIRM_PATTERN = re.compile(r"^yes$")
        service.DECLINE_PATTERN = re.compile(r"^no$")
        with patch.dict(sys.modules, {service.__name__: service}):
            self.assertFalse(namespace["response_cache_eligible"]("Which ones?"))
            self.assertFalse(namespace["response_cache_eligible"]("What other email provider can you use?"))
            self.assertFalse(namespace["response_cache_eligible"]("What other emails do I have?"))
            self.assertFalse(namespace["response_cache_eligible"]("Okay. I asked asked what other Gmails... what other emails do I have?"))

    async def test_history_environment_and_pending_authority_reach_existing_gateway(self):
        path = Path(__file__).resolve().parents[2] / "app/services/intent_gateway.py"
        source = ast.parse(path.read_text())
        node = next(n for n in source.body if isinstance(n, ast.AsyncFunctionDef) and n.name == "_propose_connector_status")
        namespace = {"CandidateVerdict": lambda **kwargs: SimpleNamespace(**kwargs), "_MATCH_CONFIDENCE": .95}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])), str(path), "exec", flags=__import__("__future__").annotations.compiler_flag), namespace)
        service = types.ModuleType("app.services.connector_status_reply_service")
        calls = []
        service.answer_connector_status_question = lambda message, **kwargs: calls.append(kwargs)
        pending = types.ModuleType("app.services.pending_reply_classifier")
        pending.has_pending_family = lambda state: bool(state.get("pending_task"))
        context = SimpleNamespace(message="Which ones?", task_state={}, org_id="org-a", client=object(), settings=object(), connected_integrations=[], conversation_history=[{"role": "user", "content": "What email connectors do I have?"}], environment_name="acceptance")
        with patch.dict(sys.modules, {service.__name__: service, pending.__name__: pending}):
            await namespace["_propose_connector_status"](context)
            self.assertEqual(calls[0]["conversation_history"], context.conversation_history)
            self.assertEqual(calls[0]["environment_name"], "acceptance")
            context.task_state = {"pending_task": {"status": "awaiting_confirm"}}
            await namespace["_propose_connector_status"](context)
            self.assertEqual(len(calls), 1)



class FullGatewayOutlookJourneyContracts(unittest.IsolatedAsyncioTestCase):
    async def test_exact_gmail_outlook_followup_uses_verified_live_rows(self):
        from app.services import intent_gateway as gateway
        from app.services import connector_status_reply_service as status

        rows = [
            {"vendor": "gmail", "execution_available": True},
            {"vendor": "microsoft365", "execution_available": False, "blocking_reason": "missing_scope"},
        ]
        history = [
            {"role": "user", "content": "Find the email about the quarterly report in Gmail."},
            {"role": "assistant", "content": "Gmail cannot complete that search with current permissions."},
        ]
        context = gateway.GatewayContext(
            message="What other email provider can you use?",
            conversation_history=history,
            task_state={},
            org_id="acceptance-org", client=object(), settings=object(),
            connected_integrations=["gmail"],
        )
        with (
            patch.object(status, "_rows_from_get_connector_status", return_value=(rows, False)) as live,
            patch.object(status, "_allowed_vendors", return_value=frozenset({"gmail", "microsoft365"})),
        ):
            decision = await gateway.evaluate_intent_gateway(context)
        self.assertEqual(decision.action, "shortcut")
        self.assertEqual(decision.candidate_id, "connector_status")
        self.assertEqual(decision.extras["verified_tool"], "getConnectorStatus")
        self.assertIn("Gmail is connected", decision.answer)
        self.assertIn("Microsoft 365 (Outlook) is configured but needs additional permissions", decision.answer)
        self.assertNotIn("Outlook is connected", decision.answer)
        live.assert_called_once()
        self.assertEqual(live.call_args.kwargs["org_id"], "acceptance-org")

    async def test_connector_status_question_does_not_approve_pending_write(self):
        from app.services import intent_gateway as gateway
        ctx = gateway.GatewayContext(
            message="What other email provider can you use?",
            task_state={"pending_task": {"status": "awaiting_confirm", "invoke_action": "gmail.messages.send"}},
            org_id="acceptance-org", client=object(), settings=object(),
            conversation_history=[{"role": "user", "content": "Draft a message but do not send it."}],
        )
        async def no_candidate(_ctx):
            return None
        with (
            patch.object(gateway, "_SYNC_CANDIDATES", ()),
            patch.object(gateway, "_propose_channel_override", side_effect=no_candidate),
            patch.object(gateway, "_propose_meta_capability", side_effect=no_candidate),
        ):
            decision = await gateway.evaluate_intent_gateway(ctx)
        self.assertEqual(decision.action, "fallthrough")
        self.assertNotEqual(decision.candidate_id, "connector_status")


if __name__ == "__main__":
    unittest.main()
