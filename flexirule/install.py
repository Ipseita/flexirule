import frappe


def after_install():
	"""
	Run setup tasks after the FlexiRule app is installed.
	"""
	setup_default_ruleflow_settings()


def setup_default_ruleflow_settings():
	"""
	Populate the RuleFlow Settings singleton with default values,
	including a default list of excluded DocTypes.
	"""
	# The DocType was just synced; clear the metadata cache so the controller
	# lookup finds flexirule.ruleflow.doctype.ruleflow_settings rather than
	# falling back to a stale or empty cache entry.
	frappe.clear_cache()
	settings = frappe.get_doc("RuleFlow Settings")

	default_doctypes = [
		"Rule",
		"Rule Execution Log",
		"Rule Scheduler",
		"Error Log",
		"Activity Log",
		"Access Log",
		"Email Queue",
		"Scheduled Job Log",
		"Version",
		"Comment",
		"Communication",
		"File",
	]

	existing_doctypes = [row.document_type for row in settings.excluded_doctypes]

	for dt in default_doctypes:
		if dt not in existing_doctypes and frappe.db.exists("DocType", dt):
			settings.append("excluded_doctypes", {"document_type": dt})

	settings.save(ignore_permissions=True)
