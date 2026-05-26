# Copyright (c) 2025, FlexiRule / Ipseita contributors
# For license information, please see license.txt

"""
Unit tests for the execute_rule_by_name programmatic execution API.

These tests exercise the path used by the CAIAC Node Side-Effect Executor
to invoke FlexiRule rules from command-trigger client_commands without a
doc-mutation event.
"""

from __future__ import annotations

import json
import unittest
from unittest.mock import MagicMock, patch

import frappe
from frappe.exceptions import MandatoryError, ValidationError


class TestExecuteRuleByName(unittest.TestCase):
    """Tests for flexirule.ruleflow.api.execute_rule_by_name"""

    def setUp(self):
        frappe.set_user("Administrator")
        if not frappe.db.exists("Rule", "Test CAIA Command Trigger Rule"):
            self.rule = frappe.get_doc(
                {
                    "doctype": "Rule",
                    "rule_name": "Test CAIA Command Trigger Rule",
                    "document_type": "ToDo",
                    "trigger_type": "Callable Event",
                    "is_active": 1,
                    "caia_command_trigger": 1,
                    "manual_dispatch_only": 1,
                    "actions": [
                        {
                            "action_type": "Stop",
                            "operation": "Success",
                            "action_label": "Stop",
                            "action_id": "action_stop",
                            "is_entry_action": 1,
                        }
                    ],
                }
            )
            self.rule.insert(ignore_permissions=True)
        else:
            self.rule = frappe.get_doc("Rule", "Test CAIA Command Trigger Rule")

    def tearDown(self):
        frappe.db.rollback()

    # ------------------------------------------------------------------ #
    # Validation: missing required arguments                               #
    # ------------------------------------------------------------------ #

    def test_missing_rule_name_raises(self):
        from flexirule.ruleflow.api import execute_rule_by_name

        with self.assertRaises(Exception):
            execute_rule_by_name("", "ToDo", "some-name")

    def test_missing_doctype_raises(self):
        from flexirule.ruleflow.api import execute_rule_by_name

        with self.assertRaises(Exception):
            execute_rule_by_name("Test CAIA Command Trigger Rule", "", "some-name")

    def test_mismatched_doctype_returns_error(self):
        from flexirule.ruleflow.api import execute_rule_by_name

        with self.assertRaises(Exception):
            execute_rule_by_name(
                "Test CAIA Command Trigger Rule",
                "Sales Order",  # wrong — rule is for ToDo
                "some-name",
            )

    def test_inactive_rule_raises(self):
        from flexirule.ruleflow.api import execute_rule_by_name

        rule = frappe.get_doc("Rule", self.rule.name)
        rule.is_active = 0
        rule.status = "Draft"
        rule.save(ignore_permissions=True)

        with self.assertRaises(Exception):
            execute_rule_by_name("Test CAIA Command Trigger Rule", "ToDo", "some-name")

    # ------------------------------------------------------------------ #
    # Happy path: rule executes and returns success shape                 #
    # ------------------------------------------------------------------ #

    def test_successful_execution_returns_success_shape(self):
        from flexirule.ruleflow.api import execute_rule_by_name

        # Create a minimal ToDo to serve as the reference document.
        todo = frappe.get_doc({"doctype": "ToDo", "description": "CAIA test"})
        todo.insert(ignore_permissions=True)

        context_vars = json.dumps(
            {
                "workflow_key": "test_caia_workflow",
                "conversation_id": "CONV-0001",
                "message_id": "MSG-0001",
            }
        )

        result = execute_rule_by_name(
            rule_name="Test CAIA Command Trigger Rule",
            reference_doctype="ToDo",
            reference_docname=todo.name,
            context_vars=context_vars,
            idempotency_key="CONV-0001:MSG-0001:test_caia_workflow:abc123",
        )

        self.assertTrue(result.get("success"), f"Expected success, got: {result}")
        self.assertIn("idempotency_key", result)
        self.assertEqual(
            result["idempotency_key"],
            "CONV-0001:MSG-0001:test_caia_workflow:abc123",
        )

    # ------------------------------------------------------------------ #
    # manual_dispatch_only suppresses doc-event hook execution            #
    # ------------------------------------------------------------------ #

    def test_manual_dispatch_only_skipped_in_doc_events(self):
        """A rule with manual_dispatch_only=1 must not fire via doc-event hooks."""
        from flexirule.ruleflow.core.coordinator import RuleCoordinator

        # Create a minimal ToDo and simulate an event cycle.
        todo = frappe.get_doc({"doctype": "ToDo", "description": "Hook skip test"})
        todo.insert(ignore_permissions=True)

        executed_rules: list[str] = []
        original = RuleCoordinator.execute_single_rule.__func__  # type: ignore[attr-defined]

        def tracking_execute(cls_or_doc, *args, **kwargs):  # noqa: ANN001
            # The first positional arg after self in the static call varies;
            # just capture rule name from kwargs or args.
            rule_arg = kwargs.get("rule_doc") or (args[1] if len(args) > 1 else None)
            if rule_arg is not None:
                executed_rules.append(getattr(rule_arg, "name", str(rule_arg)))
            return original(cls_or_doc, *args, **kwargs)

        # We don't actually patch here to keep the test simple;
        # instead verify the registry check suppresses the rule correctly.
        # A rule with manual_dispatch_only=1 should have zero executions
        # when execute_rules_from_event is called.
        original_execute = RuleCoordinator.execute_single_rule

        def capture_execute(doc, rule_doc, *args, **kwargs):
            executed_rules.append(rule_doc.name)
            return original_execute(doc, rule_doc, *args, **kwargs)

        with patch.object(RuleCoordinator, "execute_single_rule", staticmethod(capture_execute)):
            RuleCoordinator.execute_rules_from_event(todo, "After Save")

        self.assertNotIn(
            "Test CAIA Command Trigger Rule",
            executed_rules,
            "manual_dispatch_only rule must not execute via doc-event hooks",
        )
