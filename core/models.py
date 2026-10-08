from dataclasses import dataclass, field
from typing import List


@dataclass
class Flight:
    flight_id: str
    operation: str                 # "arrival" or "departure"
    eta: int                       # minutes from 10:00, e.g. 7 -> 10:07
    aircraft_type: str = "medium"  # light / medium / heavy
    fuel_status: str = "normal"    # normal / low / critical
    medical_emergency: bool = False
    preferred_runway: str = ""
    source_waypoint: str = "NORTH"

    def to_dict(self):
        return {
            "flight_id": self.flight_id,
            "operation": self.operation,
            "eta": self.eta,
            "eta_label": minute_to_clock(self.eta),
            "aircraft_type": self.aircraft_type,
            "fuel_status": self.fuel_status,
            "medical_emergency": self.medical_emergency,
            "preferred_runway": self.preferred_runway,
            "source_waypoint": self.source_waypoint,
        }


@dataclass
class Runway:
    runway_id: str
    is_open: bool = True
    allowed_types: List[str] = field(
        default_factory=lambda: ["light", "medium", "heavy"]
    )

    def to_dict(self):
        return {
            "runway_id": self.runway_id,
            "is_open": self.is_open,
            "allowed_types": self.allowed_types,
        }


def minute_to_clock(minute: int, base_hour: int = 10) -> str:
    total = base_hour * 60 + minute
    h = (total // 60) % 24
    m = total % 60
    return f"{h:02d}:{m:02d}"
