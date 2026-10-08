# Intelligent Air Traffic Management System

**Artificial Intelligence Mini Project**  
**Aryan Paode | C033 | B.Tech Computer Engineering, MPSTME, NMIMS**  
**Version:** V5

## About the project

I built this project to apply the AI algorithms we studied to one common problem instead of demonstrating them separately. The idea is to simulate a small airport where flights have to be routed and given runway slots. If a waypoint gets blocked, a runway closes, or a flight has an emergency, the schedule needs to be worked out again.

It is a **local web application** made with Python, Flask, HTML, CSS and JavaScript. The actual decisions are made using classical AI algorithms, so the simulator does not need a Gemini or other AI API to run.

This is only an academic simulation. The flight details, route penalties and separation timings are simplified for the project; they are not actual air traffic control rules.

## What is included

- **Route finding:** BFS, Uniform Cost Search, Greedy Best-First Search and A* on a waypoint graph.
- **Priority rules:** Forward chaining to decide whether a flight has Normal, High or Emergency priority.
- **Runway scheduling:** A constraint satisfaction problem (CSP) that considers available runways, flight timings and separation between aircraft.
- **Optimization:** MRV, forward checking and branch-and-bound to reduce unnecessary search and minimize priority-weighted delay.
- **Dashboard:** A radar-style view, selectable scenarios, route comparisons, runway schedules and explanations of decisions.

The route search, rule-based priority calculation and runway scheduler are connected. For example, if a route changes, its additional delay affects the earliest time at which that flight can be scheduled.

## How to run it

You need Python 3 and a web browser. Open a terminal in the extracted project folder.

**Windows:**

```powershell
py -m pip install -r requirements.txt
py app.py
```

**Mac/Linux:**

```bash
python3 -m pip install -r requirements.txt
python3 app.py
```

Open **http://127.0.0.1:5000** in your browser. Press `Ctrl+C` in the terminal to stop the application.

I am keeping the simulator as a **local demo**, not hosting the Flask application online. This GitHub repository is for the source code and for anyone who wants to reproduce the results. For an offline classroom demo, install the Python dependencies beforehand.

## Things to try

1. Start with **Normal Traffic** and check the flights and two runways.
2. Try **Search Contrast** to compare the paths found by BFS, UCS, Greedy and A*.
3. Load **Combined Disruption**. This closes R2, blocks waypoint WP1 and gives AI222 emergency priority because of critical fuel.
4. Check the route chosen for AI222, then run the runway optimizer.
5. Open the decision trace and CSP comparison to see why a flight received its slot.

Other scenarios in the simulator include runway closure, severe weather and emergency aircraft.

## Example: Combined Disruption

This is the main case I used in the report.

| Item | Result |
|---|---|
| Available runway | R1 (R2 closed) |
| Blocked waypoint | WP1 |
| Flight with critical fuel | AI222 |
| Normal route cost | 12.5 |
| New route | NORTH → WP2 → HOLD_B → AIRPORT |
| New route cost | 22.5 |
| AI222 planned ETA | 10:09 |
| Delay caused by route change | 4 minutes |
| AI222 effective ETA | 10:13 |
| Final runway slot | R1 at 10:13 |
| Additional scheduling delay for AI222 | 0 minutes |
| Priority-weighted score for all eight flights | **77** |

The four-minute route delay comes from the project's cost-to-delay formula. The more interesting part is **scheduling all eight flights on the one open runway**. Getting an effective ETA of 10:13 does not automatically reserve a runway slot at 10:13. The scheduler still has to assign the other flights while satisfying the separation rules.

In this model, priority weights are 1 (Normal), 3 (High) and 10 (Emergency). The simplified aircraft separation values are 3 minutes (Light), 4 minutes (Medium) and 5 minutes (Heavy). These values are used only for the simulation.

## Testing the result

From the project folder, run:

```bash
python reproduce_combined_case.py
python -m pytest -q
```

On Windows, you can use `py` instead of `python` in these two commands.

- `reproduce_combined_case.py` runs the combined scenario, checks AI222's route, priority and final schedule, and compares the answer with the exact single-runway validator.
- `tests/test_core.py` contains **14 automated tests** for the main algorithms and integration.
- `evidence/combined_disruption_verified.txt` contains the saved output of the reproducibility script.

The exact validator in `core/validator.py` checks **8! = 40,320** possible flight orderings for this eight-flight, single-runway case. It also finds a minimum weighted score of **77**. This is a check for the defined academic problem, not a claim about real airport performance.

I also compared the result with a separate **SkyRoute ATC** application created through Google AI Studio:  
https://ais-pre-hzbqjwkt3kbgipkx2hcbxi-630923407153.asia-east1.run.app/

Both applications show AI222 at R1 at 10:13 with a weighted score of 77. The SkyRoute app uses predefined optimal schedules, so I use it as a comparison of results; the complete 40,320-ordering check is in this repository.

## Main files

| File or folder | Purpose |
|---|---|
| `app.py` | Flask application |
| `core/search.py` | BFS, UCS, Greedy and A* |
| `core/knowledge.py` | Forward-chaining priority rules |
| `core/integration.py` | Route changes and effective ETA |
| `core/scheduler.py` | Runway scheduling and CSP comparison |
| `core/validator.py` | Exhaustive single-runway check |
| `core/explain.py` | Explanations and delay values |
| `core/scenarios.py` | Flight data and preset scenarios |
| `templates/`, `static/` | Web interface |
| `tests/` | Automated tests |
| `reproduce_combined_case.py` | Reproduces the main case result |

The `CHANGELOG_V2.md` to `CHANGELOG_V5.md` files record the revisions made during development.

## Note

This was made for learning search algorithms, logical inference and constraint optimization. It does **not** use live flight data or implement actual aviation regulations. The Flask app also keeps scenario state in memory, so it is intended for running locally by one user at a time.
