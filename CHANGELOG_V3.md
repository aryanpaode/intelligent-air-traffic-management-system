# Version 3 Changelog

## Scheduling intelligence

- Replaced the first-valid CSP scheduler with a **priority-weighted optimization CSP**.
- Objective: minimize `Σ(delay × priority weight)`.
- Priority weights: Normal = 1, High = 3, Emergency = 10.
- Added branch-and-bound pruning.
- Retained MRV variable ordering.
- Added forward checking / constraint propagation.
- Added least-cost value ordering.
- Added detailed metrics: candidate assignments, constraint checks, backtracks, forward checks, branches pruned, weighted cost, average delay, emergency delay, and runtime.

## CSP strategy laboratory

Added a comparison of:

1. Plain Backtracking
2. Backtracking + MRV
3. MRV + Forward Checking

The comparison deliberately reports first-feasible search statistics so the effect of heuristics can be discussed independently from the optimization objective.

## Search-to-scheduling integration

- A* now evaluates the current arrival route for each incoming flight.
- A pristine airspace graph supplies a baseline route cost.
- Extra route cost from weather/risk/congestion is converted into a small simulated route delay.
- The resulting **effective ETA** is passed into the CSP optimizer.
- The original planned ETA is never overwritten.
- The UI separates `Route Δ` from subsequent `CSP Delay`.

This creates the V3 flow:

`Weather / risk -> A* route -> Effective ETA -> CSP optimizer -> runway slot`

## Scenario changes

- Severe Weather now blocks WP1 and makes the eastern approach riskier, creating a visible route-induced ETA shift for NORTH arrivals.
- Combined Disruption combines the route effect with R2 closure and an emergency-priority flight.
- Search Contrast remains dedicated to BFS/UCS/Greedy/A* comparison.

## Interface redesign

The V2 navy/cyan "AI dashboard" palette has been replaced with a warmer **airfield operations / control-room** scheme:

- warm parchment background
- charcoal/olive radar
- amber route highlighting
- terracotta primary controls
- sage normal status
- mustard high-priority status
- brick-red emergency status

No generative-AI visual styling or neon-cyan theme is used.
