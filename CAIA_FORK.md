# CAIA Fork of FlexiRule

This is the Ipseita fork of [Sendipad/flexirule](https://github.com/Sendipad/flexirule),
vendored into the CAIAC bench at `caiac/frappe-bench/apps/flexirule`.

## What this fork adds

| Change | File(s) | Upstream PR candidate? |
|--------|---------|------------------------|
| `execute_rule_by_name` whitelisted API | `flexirule/ruleflow/api.py` | **Yes — priority 1** |
| `manual_dispatch_only` Rule field | `flexirule/ruleflow/doctype/rule/rule.json`, `core/coordinator.py` | **Yes — priority 2** |
| `caia_command_trigger` Rule field (marker) | `flexirule/ruleflow/doctype/rule/rule.json` | Optional / lower priority |
| `is_fixture` Rule field | `flexirule/ruleflow/doctype/rule/rule.json` | Optional / lower priority |
| Tests for programmatic invocation | `flexirule/ruleflow/tests/test_execute_rule_by_name.py` | Yes (with upstream tests) |

## Upstream contribution plan

1. Open a PR to upstream for `execute_rule_by_name`:
   - Programmatic invocation without a document-mutation event.
   - Useful for any caller that wants to run a rule from external triggers,
     scheduled jobs, or API calls without needing to save a document first.

2. Open a PR for `manual_dispatch_only`:
   - Prevents a rule from firing via doc-event hooks; it can only be invoked
     explicitly via `execute_rule_by_name` or the test API.
   - Useful for rules that should only run on explicit operator approval.

3. Contribute Frappe v15 compatibility fixes discovered during integration
   (document as they arise).

## Tracking divergence

Keep this file updated whenever a fork-only change is made.  Before merging
any upstream release into this fork, check each entry in the table above and
determine whether the upstream version supersedes the fork change.

## Upgrade procedure

```bash
cd caiac/frappe-bench/apps/flexirule
git fetch origin
git merge origin/develop   # or the relevant release tag
# Resolve conflicts; re-apply fork-only changes if lost
# Run: cd ../.. && ./env/bin/bench migrate
# Run: ./env/bin/bench restart  (not full container restart)
```
