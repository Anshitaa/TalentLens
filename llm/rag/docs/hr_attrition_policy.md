# HR Attrition Risk Policy

## Purpose and Scope

This policy governs how TalentLens identifies, monitors, and responds to employee attrition risk. It applies to all full-time employees and is administered jointly by HR Business Partners and direct managers. The goal is to enable proactive intervention before voluntary separations occur, reducing turnover costs and preserving organizational knowledge.

## Risk Tier Definitions

TalentLens classifies each active employee into one of four attrition risk bands based on the composite Risk Index score (0–100):

| Band | Risk Index Range | Meaning |
|------|-----------------|---------|
| Low | 0–39 | No immediate concern; standard engagement check-ins apply |
| Medium | 40–59 | Monitor closely; schedule a stay interview within 60 days |
| High | 60–79 | Elevated flight risk; immediate manager notification required |
| Critical | 80–100 | Imminent departure likely; escalate to HR BP within 24 hours |

## Manager Notification Procedures

When an employee's risk band changes to **High**, the system automatically generates a confidential alert sent to the employee's direct manager and the assigned HR Business Partner. The manager must:

1. Acknowledge the alert within 48 hours via the TalentLens dashboard.
2. Schedule a one-on-one check-in meeting within 7 calendar days.
3. Document conversation notes in the HRIS (notes are visible only to HR and the manager).
4. Submit an initial retention intent assessment — whether active retention action is warranted.

When an employee's risk band changes to **Critical**, escalation goes directly to the HR Director and VP of the relevant business unit in addition to the manager. A mandatory 24-hour response window applies.

## 90-Day Action Plans for High and Critical Risk Employees

For all employees flagged as High or Critical risk, a formal 90-Day Retention Action Plan must be created within 14 days of the initial flag. The plan must include:

- **Root cause hypothesis**: Based on SHAP feature attributions (e.g., low peer pay percentile, tenure milestone, recent performance dip, low manager rating), identify the likely driver(s) of elevated risk.
- **Targeted intervention**: Select at least two retention levers from the approved menu: compensation review, role expansion, internal transfer opportunity, flexible work arrangement, recognition program nomination, or mentorship pairing.
- **Check-in cadence**: Weekly manager check-ins for Critical employees; bi-weekly for High.
- **30/60/90-day milestones**: Concrete, measurable leading indicators that signal improving engagement (e.g., increased project participation, peer rating improvement).
- **Exit trigger**: If risk index remains ≥ 70 at the 90-day mark despite interventions, the HR BP escalates to a formal succession planning discussion.

## Confidentiality Requirements

All attrition risk data is classified as **HR Confidential**. Risk bands must not be shared with the employee, their colleagues, or any manager outside the direct reporting chain without explicit approval from the CHRO. Violation of this policy may result in disciplinary action.

## Model Override and Appeal

Managers who believe a risk score is inaccurate may submit a manual override via the HITL (Human-in-the-Loop) workflow. All overrides are logged in the audit schema and factored into model retraining on a quarterly cycle.

## Policy Review Cadence

This policy is reviewed semi-annually by the HR Analytics team and updated to reflect changes in model performance, business strategy, or employment law.
