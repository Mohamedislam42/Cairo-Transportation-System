# traffic_predictor.py
from __future__ import annotations
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import LabelEncoder
from transport_core import TRAFFIC_PATTERNS, EXISTING_ROADS

# Build a lookup for road capacity and condition
road_info: dict[str, tuple[int, int]] = {}
for r in EXISTING_ROADS:
    key = f"{r.src}-{r.dst}"
    road_info[key] = (r.capacity_vph, r.condition)
    road_info[f"{r.dst}-{r.src}"] = (r.capacity_vph, r.condition)

SLOT_MAP = {"morning": 0, "afternoon": 1, "evening": 2, "night": 3}

def _build_dataset():
    X, y = [], []
    for road_id, pattern in TRAFFIC_PATTERNS.items():
        cap, cond = road_info.get(road_id, (2000, 7))
        for slot_name, slot_idx in SLOT_MAP.items():
            flow = getattr(pattern, slot_name)
            X.append([slot_idx, cap, cond])
            y.append(flow)
    return np.array(X), np.array(y)

class TrafficPredictor:
    def __init__(self):
        X, y = _build_dataset()
        self.model = RandomForestRegressor(n_estimators=100, random_state=42)
        self.model.fit(X, y)

    def predict(self, slot: str, capacity: int, condition: int) -> int:
        slot_idx = SLOT_MAP.get(slot, 1)
        pred = self.model.predict([[slot_idx, capacity, condition]])[0]
        return max(0, int(round(pred)))

    def predict_all_slots(self, capacity: int, condition: int) -> dict[str, int]:
        return {slot: self.predict(slot, capacity, condition) for slot in SLOT_MAP}