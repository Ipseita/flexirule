# Copyright (c) 2026, FlexiRule and contributors
# For license information, please see license.txt

"""
Runtime-safe evaluators used by the rule engine.

Splits boolean condition evaluation from value evaluation so callers can
explicitly choose semantics.

IMPORTANT: These functions log all evaluation failures to Frappe's Error Log
and the application logger so operators can diagnose silent rule divergence.
A caught exception here means the rule's condition/value *did not* evaluate
as intended — callers receive a safe default, but the failure is always
recorded for forensic analysis.
"""

from __future__ import annotations

from typing import Any

import frappe


class ReadOnlyDocument:
	"""Proxy for Document that prevents mutation"""

	def __init__(self, doc):
		object.__setattr__(self, "_doc", doc)

	def __getattr__(self, name):
		return getattr(self._doc, name)

	def __getitem__(self, key):
		return self._doc[key]

	def get(self, key, default=None):
		return self._doc.get(key, default)

	def __setattr__(self, name, value):
		raise frappe.ValidationError("Cannot mutate document in Pure method")

	def __setitem__(self, key, value):
		raise frappe.ValidationError("Cannot mutate document in Pure method")

	def save(self, *args, **kwargs):
		raise frappe.ValidationError("Cannot save document in Pure method")

	def insert(self, *args, **kwargs):
		raise frappe.ValidationError("Cannot insert document in Pure method")

	def delete(self, *args, **kwargs):
		raise frappe.ValidationError("Cannot delete document in Pure method")

	def db_set(self, *args, **kwargs):
		raise frappe.ValidationError("Cannot db_set document in Pure method")

	def run_method(self, *args, **kwargs):
		raise frappe.ValidationError("Cannot run_method on document in Pure method")

	def add_comment(self, *args, **kwargs):
		raise frappe.ValidationError("Cannot add_comment on document in Pure method")

	def queue_action(self, *args, **kwargs):
		raise frappe.ValidationError("Cannot queue_action on document in Pure method")

	@property
	def flags(self):
		import copy

		return copy.deepcopy(self._doc.flags)


class SafeFrappeAPI:
	"""
	Restricted Frappe API proxy for rule condition evaluation.
	Exposes only safe, read-only operations to prevent security issues.
	"""

	def __init__(self):
		# Safe utilities
		self.utils = frappe.utils
		self._dict = frappe._dict

	@property
	def session(self):
		"""Read-only access to frappe.session (current user, roles, etc.)"""
		return frappe.session

	@staticmethod
	def get_roles(user=None):
		"""Read-only: return roles for the given user (or current session user)."""
		return frappe.get_roles(user)

	# Safe read operations
	@staticmethod
	def get_value(doctype, filters, fieldname=None, **kwargs):
		"""Read-only get_value"""
		return frappe.get_value(doctype, filters, fieldname, **kwargs)

	@staticmethod
	def get_all(doctype, filters=None, fields=None, limit_page_length=500, **kwargs):
		"""Read-only get_all with default limit"""
		if "limit" in kwargs:
			limit_page_length = kwargs.pop("limit")
		return frappe.get_all(
			doctype, filters=filters, fields=fields, limit_page_length=limit_page_length, **kwargs
		)

	@staticmethod
	def db_exists(doctype, name):
		"""Check if document exists"""
		return frappe.db.exists(doctype, name)

	@staticmethod
	def get_meta(doctype):
		"""Get doctype metadata"""
		return frappe.get_meta(doctype)

	@staticmethod
	def format_value(value, df=None, doc=None, currency=None):
		"""Format value for display"""
		return frappe.format_value(value, df, doc, currency)

	# Logging (safe)
	@staticmethod
	def log(message):
		"""Log a message"""
		frappe.logger().info(message)

	# Explicitly denied operations (will raise)
	def get_doc(self, *args, **kwargs):
		raise PermissionError("get_doc is not allowed in rule conditions. Use frappe.get_value instead.")

	def new_doc(self, *args, **kwargs):
		raise PermissionError("new_doc is not allowed in rule conditions.")

	def delete_doc(self, *args, **kwargs):
		raise PermissionError("delete_doc is not allowed in rule conditions.")

	def db_set_value(self, *args, **kwargs):
		raise PermissionError("db.set_value is not allowed in rule conditions.")

	@property
	def db(self):
		"""Return restricted db proxy"""
		return self._SafeDB()

	class _SafeDB:
		"""Restricted database operations"""

		def exists(self, doctype, name):
			return frappe.db.exists(doctype, name)

		def get_value(self, doctype, filters, fieldname=None, **kwargs):
			return frappe.db.get_value(doctype, filters, fieldname, **kwargs)

		def get_all(self, doctype, filters=None, fields=None, **kwargs):
			return frappe.db.get_all(doctype, filters=filters, fields=fields, **kwargs)

		# Explicitly deny write operations
		def set_value(self, *args, **kwargs):
			raise PermissionError("db.set_value is not allowed in rule conditions.")

		def sql(self, *args, **kwargs):
			raise PermissionError("db.sql is not allowed in rule conditions.")

		# Transaction control restricted (following Frappe restrict_commit_rollback)
		def commit(self, *args, **kwargs):
			raise PermissionError("db.commit is not allowed during doc event rules.")

		def rollback(self, *args, **kwargs):
			raise PermissionError("db.rollback is not allowed during doc event rules.")

		def add_index(self, *args, **kwargs):
			raise PermissionError("db.add_index is not allowed during doc event rules.")


# Singleton instance
_safe_frappe = SafeFrappeAPI()


def _get_meta(doctype):
	if not doctype:
		return None
	try:
		return frappe.get_meta(doctype)
	except Exception:
		return None


def _is_submittable(doctype):
	meta = _get_meta(doctype)
	return bool(getattr(meta, "is_submittable", 0)) if meta else False


def _has_field(doctype, fieldname):
	meta = _get_meta(doctype)
	return bool(meta and fieldname and meta.has_field(fieldname))


def _length_of(value):
	if value is None:
		return 0
	if isinstance(value, str):
		return len(value.strip())
	if isinstance(value, list | tuple | dict | set):
		return len(value)
	try:
		return len(value)
	except Exception:
		return 0


def _is_empty_value(value):
	if value is None:
		return True
	if isinstance(value, str):
		return value.strip() == ""
	if isinstance(value, list | tuple | dict | set):
		return len(value) == 0
	return False


def get_base_eval_context(doc: Any, old_doc: Any = None, vars_dict: dict | None = None) -> dict:
	"""
	Build optimized base context for all evaluation points.
	Injects shared helpers and SafeFrappeAPI singleton.
	"""
	from flexirule.ruleflow.core.evaluator import check_link_match
	from flexirule.ruleflow.utils.field_resolver import FieldResolver

	if isinstance(doc, dict):
		doc = frappe._dict(doc)
	if isinstance(old_doc, dict):
		old_doc = frappe._dict(old_doc)

	return {
		"doc": doc,
		"old_doc": old_doc,
		"vars": vars_dict if vars_dict is not None else {},
		"frappe": _safe_frappe,
		"is_submittable": _is_submittable,
		"has_field": _has_field,
		"get_meta": _get_meta,
		"resolve": FieldResolver.resolve,
		"check_link_match": check_link_match,
		"length_of": _length_of,
		"is_empty_value": _is_empty_value,
		"any": any,
		"all": all,
		"True": True,
		"False": False,
		"None": None,
	}


def eval_condition_bool(expression: str, safe_locals: dict, default: bool = False) -> bool:
	"""Evaluate expression and coerce to bool.

	On failure, logs the expression and exception details to both
	``frappe.logger`` and the Error Log DocType, then returns *default*.
	"""
	if not expression:
		return True

	try:
		return bool(frappe.safe_eval(expression, None, safe_locals))
	except Exception as exc:
		_log_eval_failure("eval_condition_bool", expression, exc)
		return default


def eval_value(expression: str, safe_locals: dict, default=None):
	"""Evaluate expression and return raw value.

	On failure, logs the expression and exception details to both
	``frappe.logger`` and the Error Log DocType, then returns *default*.
	"""
	if not expression:
		return default

	try:
		return frappe.safe_eval(expression, None, safe_locals)
	except Exception as exc:
		_log_eval_failure("eval_value", expression, exc)
		return default


def _log_eval_failure(func_name: str, expression: str, exc: Exception) -> None:
	"""Centralised logging for evaluation failures.

	Writes to both:
	- ``frappe.logger("flexirule.eval")`` — for application-level log files.
	- ``frappe.log_error`` — for the Error Log DocType, giving operators
	  UI-visible traceability.

	The expression is truncated to 500 chars to avoid log bloat from
	extremely large compiled expressions.
	"""
	truncated_expr = expression[:500] + ("…" if len(expression) > 500 else "")
	message = f"FlexiRule {func_name} failed.\n" f"Expression: {truncated_expr}\n" f"Error: {exc!s}"

	frappe.logger("flexirule.eval").warning(message)
	frappe.log_error(
		title=f"FlexiRule Expression Evaluation Error ({func_name})",
		message=message,
	)
