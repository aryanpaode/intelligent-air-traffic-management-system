"""
Forward-chaining knowledge engine used by the ATC academic simulation.

V5 exposes rule identifiers and fired-rule traces so the interface can show
exactly which symbolic rules produced each inferred priority.
"""


def infer_flight_priority(flight):
    facts = {
        ("operation", flight.operation),
        ("fuel", flight.fuel_status),
        ("aircraft_type", flight.aircraft_type),
    }

    if flight.medical_emergency:
        facts.add(("medical_emergency", True))

    explanations = []
    rules_fired = []

    def fire(rule_id, condition, conclusion, explanation):
        rules_fired.append({
            "rule_id": rule_id,
            "condition": condition,
            "conclusion": conclusion,
            "explanation": explanation,
        })
        explanations.append(explanation)

    changed = True
    while changed:
        changed = False

        # R1: Critical fuel implies emergency status.
        if ("fuel", "critical") in facts and ("emergency", True) not in facts:
            facts.add(("emergency", True))
            fire(
                "R1",
                "fuel = critical",
                "emergency = true",
                "Critical fuel triggered the emergency-status rule.",
            )
            changed = True

        # R2: A medical emergency also implies emergency status.
        if ("medical_emergency", True) in facts and ("emergency", True) not in facts:
            facts.add(("emergency", True))
            fire(
                "R2",
                "medical_emergency = true",
                "emergency = true",
                "Medical emergency triggered the emergency-status rule.",
            )
            changed = True

        # R3: Low fuel receives high priority.
        if ("fuel", "low") in facts and ("priority", "high") not in facts:
            facts.add(("priority", "high"))
            fire(
                "R3",
                "fuel = low",
                "priority = high",
                "Low fuel raised the flight to high priority.",
            )
            changed = True

        # R4: Emergency status overrides high/normal priority.
        if ("emergency", True) in facts and ("priority", "emergency") not in facts:
            facts.discard(("priority", "high"))
            facts.add(("priority", "emergency"))
            fire(
                "R4",
                "emergency = true",
                "priority = emergency",
                "Emergency status produced the highest scheduling priority.",
            )
            changed = True

        # R5: Default normal priority if no stronger rule applies.
        if (
            ("priority", "emergency") not in facts
            and ("priority", "high") not in facts
            and ("priority", "normal") not in facts
        ):
            facts.add(("priority", "normal"))
            fire(
                "R5",
                "no emergency/high-priority condition is present",
                "priority = normal",
                "No emergency or high-priority rule applied; normal priority was inferred.",
            )
            changed = True

    if ("priority", "emergency") in facts:
        priority = "emergency"
        rank = 0
    elif ("priority", "high") in facts:
        priority = "high"
        rank = 1
    else:
        priority = "normal"
        rank = 2

    return {
        "priority": priority,
        "priority_rank": rank,
        "facts": sorted([f"{k}={v}" for k, v in facts]),
        "explanations": explanations,
        "rules_fired": rules_fired,
    }


def runway_knowledge(runways):
    facts = []
    explanations = []
    for runway in runways:
        status = "open" if runway.is_open else "closed"
        facts.append(f"{runway.runway_id}={status}")
        if not runway.is_open:
            explanations.append(
                f"{runway.runway_id} is closed, so the CSP must not assign it."
            )
    return {"facts": facts, "explanations": explanations}
