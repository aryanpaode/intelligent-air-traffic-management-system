# Intelligent Air Traffic Management System (V5)

**Classical AI | Search, rule-based reasoning, constraint satisfaction and runway optimization**

**Author:** Aryan Paode (C033)  
**Course:** Artificial Intelligence — B.Tech Computer Engineering, MPSTME, NMIMS University  
**Version:** V5 (objective-bounded optimizer)  
**Project type:** Academic simulation; **runs locally** on a laptop

> **Academic boundary:** This is a simplified educational simulator, **not** certified air traffic control software. Route costs, route-delay conversion, aircraft separation intervals and priority weights are synthetic. It does not use real airport feeds, operational regulations, or live control of aircraft.

## What the project does

The simulator integrates three forms of classical Artificial Intelligence to respond to disruptions in a small artificial airspace:

1. **Graph search:** BFS, Uniform Cost Search, Greedy Best-First Search and A* compare routes through a weighted waypoint network. A* is used for route reassessment when simulated weather changes an approach.
2. **Knowledge-based inference:** Explicit forward-chaining rules R1–R5 infer Normal, High or Emergency priority from fuel and medical-emergency facts.
3. **Constraint satisfaction and optimization:** Flights receive feasible `(runway, time)` assignments subject to runway availability, aircraft compatibility, effective ETA and simplified same-runway separation. A priority-weighted optimizer minimizes scheduler-induced delay using branch-and-bound, MRV and forward checking.

The browser dashboard visualizes radar/waypoints, flight and runway states, selected routes, scheduling results, comparisons and per-flight decision traces. **No Gemini or other generative-AI API is required to run this simulator.**

## Local demonstration (no website hosting)

The **public GitHub repository is the source-code and reproducibility evidence**. It is deliberately **not** a hosted application. During presentations, launch Flask on the presenter's computer and open the local browser dashboard.

**Prerequisites:** Python 3.11 or newer, pip, and a browser. Installation of Python packages needs network access unless already cached; operation itself does not depend on an external AI API.

### Windows PowerShell

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python app.py
```

If PowerShell blocks script activation, use the virtual-environment Python directly:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python app.py
```

Open **http://127.0.0.1:5000**. Stop the server with `Ctrl+C`. To prepare for a no-internet presentation, install dependencies and test the app before arriving.

### Suggested presentation sequence

1. Open **Normal Traffic** to show the starting state and the two runways.
2. Select **Search Contrast** and compare BFS, UCS, Greedy and A*.
3. Select **Combined Disruption** to close R2, block WP1, apply weather risk and make AI222 an emergency.
4. Show A* route reassessment and forward-chaining rule explanations.
5. Select **Optimize Schedule** to generate the eight-flight feasible schedule; inspect AI222's decision trace and separation constraints.
6. Run the CSP comparison separately; its fixed-horizon heuristic benchmark is **not** the primary optimizer's runtime measurement.

## Reproduce the documented combined-disruption result

```bash
python reproduce_combined_case.py
python -m pytest -q
```

`reproduce_combined_case.py` computes the expected results using the supplied V5 source, asserts the final optimum and performs the built-in exhaustive eight-flight single-runway validation. See [`evidence/combined_disruption_verified.txt`](evidence/combined_disruption_verified.txt) for its saved output. The Python script and test suite are reproducibility checks; the core scheduler and its test suite are the original V5 implementation.

### Route calculation and inferred priority

| Item | Output |
|---|---|
| Scenario | R1 open, R2 closed, WP1 blocked, risk on HOLD_B |
| AI222 fuel / priority | Critical / Emergency (weight 10) |
| Normal route | NORTH → WP1 → HOLD_A → AIRPORT |
| Normal route cost | 12.5 |
| Disrupted route | NORTH → WP2 → HOLD_B → AIRPORT |
| Disrupted route cost | 22.5 |
| Additional route cost | 10.0 |
| Route-induced delay | ceil(10.0 / 3) = **4 minutes** |
| Planned → effective ETA | **10:09 → 10:13** |

### Final runway assignments (one optimal order)

| Flight | Effective time | Assigned R1 slot | Scheduler delay (min) | Weighted penalty |
|---|---|---|---:|---:|
| 6E204 | 10:03 | 10:03 | 0 | 0 |
| UK315 | 10:05 | 10:08 | 3 | 3 |
| **AI222** | **10:13** | **10:13** | **0** | **0** |
| SG410 | 10:07 | 10:17 | 10 | 10 |
| QP113 | 10:14 | 10:20 | 6 | 6 |
| AI101 | 10:04 | 10:24 | 20 | 20 |
| 6E880 | 10:11 | 10:28 | 17 | 17 |
| EK502 | 10:12 | 10:33 | 21 | 21 |
| **TOTAL** | | | | **77** |

**Do not confuse ETA arithmetic with scheduling:** adding four minutes yields AI222's *earliest eligible time* (10:13). The solver must also find a feasible assignment for the other seven flights while minimizing the system-wide weighted penalty. AI222 has **4 minutes route-induced delay, 0 minutes scheduler delay and 4 minutes total simulated delay**.

## Model equations

The directed-weight calculation for each traversed edge is:

```text
edge_cost(u,v) = distance(u,v) + 2.5*risk(v) + 1.5*congestion(v)
route_delay = ceil(max(0, current_route_cost - baseline_route_cost) / 3)
effective_ETA = planned_ETA + route_delay
```

For each aircraft `i`, the scheduling objective is:

```text
scheduler_delay(i) = assigned_time(i) - effective_ETA(i)
minimize J = sum(priority_weight(i) * scheduler_delay(i))
```

Priority weights: **Normal = 1; High = 3; Emergency = 10.** Simplified same-runway separation categories: **Light = 3 min; Medium = 4 min; Heavy = 5 min**; between two aircraft the required gap is the larger of their category values. These are academic rules, not actual ATC standards. Every aircraft must receive a feasible assignment and an emergency does not bypass the hard constraints.

## Verification and experimental comparisons

- **14 automated tests** (`tests/test_core.py`) cover inference, routing, changes to effective ETA, optimization, CSP heuristics, explanations, exact validation and core behaviors.
- **Built-in exact validator:** `core/validator.py` checks **8! = 40,320** permutations in the eight-flight, one-open-runway scenario and confirms the same minimum weighted cost **77**. It uses an independent single-runway permutation procedure, separate from the main optimizer.
- **Search Contrast:** BFS → cost 30.0 / 7 nodes; UCS → 12.5 / 6 nodes; Greedy → 30.0 / 4 nodes; A* → 12.5 / 4 nodes.
- **CSP efficiency comparison** (separate controlled bounded test): Plain backtracking = 4,938 backtracks; +MRV = 253; +MRV and forward checking = 102. These figures compare search work; reported runtimes are machine-dependent and must not be presented as a speedup of the main objective-bounded optimizer.

## Project layout

```text
app.py                         Flask app and local JSON endpoints
core/scenarios.py              Input flights, simulated airspace and scenario selection
core/search.py                 BFS, UCS, Greedy and A*
core/knowledge.py              Forward-chaining facts and rules
core/integration.py            A*-derived route impact and effective ETA
core/scheduler.py              CSP, objective-bounded optimization and benchmark
core/validator.py              Exact small-case one-runway cross-check
core/explain.py                Per-flight decision trace and delay metrics
core/models.py                 Flight and runway data definitions
static/app.js                  Browser interactions and radar visualization
static/style.css               UI styles
templates/index.html           Dashboard template
tests/test_core.py              Automated tests
reproduce_combined_case.py     Reproducibility runner (does not alter V5 logic)
evidence/combined_disruption_verified.txt  Recorded runner output
CHANGELOG_V2.md ... V5.md      Revision history
requirements.txt               Flask and pytest dependencies
```

## External validation reference

A separately created **SkyRoute ATC Optimization Engine** app was developed through Google AI Studio and is available at:

https://ais-pre-hzbqjwkt3kbgipkx2hcbxi-630923407153.asia-east1.run.app/

It displays the same AI222 slot (R1 at 10:13), scheduler delay (0) and weighted score (77). Its exported source uses four predefined candidate optimal orders rather than performing its own complete 40,320-order search at runtime. Accordingly, it is presented as a **reference implementation with matching results**, *not* proof that the deployed application executes a live Gemini model or independently enumerates all schedules. The V5 built-in exact validator provides the separate mathematical cross-check.

## Scope and safety limitations

This repository is an academic demonstration of classical AI, not production aviation software. There is no live surveillance or meteorological feed, certified aircraft separation, regulatory compliance, safety assurance or airport deployment. The Flask app uses single-process shared scenario state and the development server; run it **locally for an individual classroom demonstration**, not as an exposed public multi-user service.

## References

- S. Russell and P. Norvig, *Artificial Intelligence: A Modern Approach*, 4th ed., Pearson.
- P. E. Hart, N. J. Nilsson and B. Raphael, “A Formal Basis for the Heuristic Determination of Minimum Cost Paths,” *IEEE Transactions on Systems Science and Cybernetics*, 1968.
- R. Dechter, *Constraint Processing*, Morgan Kaufmann, 2003.
- A. K. Mackworth, “Consistency in Networks of Relations,” *Artificial Intelligence*, 1977.
