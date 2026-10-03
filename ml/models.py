from dataclasses import dataclass
from datetime import datetime

@dataclass
class WeatherObservation:
    timestamp: datetime
    value: float
    quality: str