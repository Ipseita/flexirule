2025-05-24 - [Efficiency] Rule Eligibility and Evaluation Environment Optimization

Learning: Orchestrating a large number of rules across document events suffers from high overhead due to eager document hydration and repeated creation of the evaluation environment (helpers, SafeFrappeAPI instances, etc.).

Reasoning: Every document event triggers a scan of potentially applicable rules. Hydrating the full Rule document (including child tables) just to check a trigger condition is expensive. Additionally, defining helper functions and re-instantiating SafeFrappeAPI for every evaluation adds significant object churn and CPU overhead in the hot path.

Action:
1. Defer Rule document hydration until after eligibility check (Lazy Hydration) by using runtime registry specs.
2. Extract common evaluation helpers to a shared location to avoid re-definition.
3. Reuse SafeFrappeAPI singleton across RuleCoordinator and RuleEngine.
4. Normalize and optimize evaluation context building to reduce redundant work per rule execution.
