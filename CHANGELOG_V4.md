# Version 4 Changelog

## Explainable AI Decision Trace

V4 adds a dedicated end-to-end explanation panel for each scheduled flight. A flight can be selected from a dropdown or opened directly from the schedule table using the **Trace** button.

The trace follows six deterministic stages:

1. **Observed Facts** — operation, aircraft type, planned ETA, fuel and source waypoint.
2. **Forward Chaining** — the symbolic rules that fired and the inferred scheduling priority.
3. **A* Route Assessment** — baseline route, current route, route cost, blocked waypoints, route delay and effective ETA.
4. **CSP Domain & Constraints** — open/closed runways, legal runway domain, earliest legal time and separation constraints.
5. **Priority-Weighted Optimization** — selected runway/time, CSP delay, weighted contribution and branch-and-bound context.
6. **Final Decision** — final assignment and explicit route-delay + CSP-delay decomposition.

## Rule transparency

The forward-chaining engine now exposes stable rule IDs:

- **R1**: critical fuel → emergency
- **R2**: medical emergency → emergency
- **R3**: low fuel → high priority
- **R4**: emergency → emergency scheduling priority
- **R5**: no stronger condition → normal priority

This makes the knowledge-representation component visible and viva-friendly instead of showing only natural-language summaries.

## Delay-metric clarification

The optimizer dashboard now distinguishes:

- Average Route Delay
- Average CSP Delay
- Average Total Delay
- Emergency CSP Delay
- Emergency Total Delay

`Emergency Delay` was renamed to **Emergency CSP Delay** to avoid confusing route delay with scheduler delay.

The schedule table also renames the objective contribution to **Weighted CSP** because the optimization objective operates on post-route scheduling delay.

## UI presentation

- Added a dedicated Explainable AI section.
- Added a Facts → Forward Chaining → A* → CSP → Optimization → Decision pipeline strip.
- Added one-click Trace buttons in the optimized schedule.
- Moved the older compact rationale cards into a collapsible details panel to reduce clutter.
- Retained the warm airfield/control-room palette introduced in V3.
