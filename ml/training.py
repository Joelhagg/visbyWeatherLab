from dataclasses import dataclass
from datetime import date, datetime
import math

from models import WeatherObservation


@dataclass
class WeatherTrainingSample:
    date: date
    temperature: float
    previous_temperature: float
    month: int
    day_of_year: int

@dataclass
class ModelResult:
    trained_at: datetime
    mae: float
    training_samples: int
    features: list[str]


def get_midday_observation(
    observations: list[WeatherObservation],
    target_date: date,
) -> WeatherObservation | None:

    for hour in [12, 13]:
        for observation in observations:
            if (
                observation.timestamp.date() == target_date
                and observation.timestamp.hour == hour
                and observation.timestamp.minute == 0
            ):
                return observation

    return None


def get_midday_observations(
    observations: list[WeatherObservation],
) -> list[WeatherObservation]:

    observations_by_date: dict[
        date,
        list[WeatherObservation],
    ] = {}

    for observation in observations:
        observation_date = observation.timestamp.date()

        observations_by_date.setdefault(
            observation_date,
            [],
        ).append(observation)

    midday_observations = []

    for observation_date, daily_observations in (
        observations_by_date.items()
    ):
        midday_observation = get_midday_observation(
            daily_observations,
            observation_date,
        )

        if midday_observation:
            midday_observations.append(
                midday_observation
            )

    return midday_observations


def build_training_samples(
    observations: list[WeatherObservation],
) -> list[WeatherTrainingSample]:

    midday_observations = get_midday_observations(
        observations
    )

    observations_by_date = {
        observation.timestamp.date(): observation
        for observation in midday_observations
    }

    samples = []

    for observation in midday_observations:
        observation_date = observation.timestamp.date()
        previous_date = observation_date.fromordinal(
            observation_date.toordinal() - 1,
        )

        previous_observation = observations_by_date.get(previous_date)

        if previous_observation is None:
            continue

        samples.append(
            WeatherTrainingSample(
                date=observation_date,
                temperature=observation.value,
                previous_temperature=previous_observation.value,
                month=observation_date.month,
                day_of_year=observation_date.timetuple().tm_yday,
            )
        )

    return samples

def build_features(
    samples: list[WeatherTrainingSample],
) -> list[list[float]]:

    return [
        [
            math.sin(
                2 * math.pi * sample.day_of_year / 365,
            ),
            math.cos(
                2 * math.pi * sample.day_of_year / 365,
            ),
            sample.previous_temperature,
        ]
        for sample in samples
    ]


def build_targets(
    samples: list[WeatherTrainingSample],
) -> list[float]:

    return [
        sample.temperature
        for sample in samples
    ]

def split_training_data(
    samples: list[WeatherTrainingSample],
    train_ratio: float = 0.8,
) -> tuple[
    list[WeatherTrainingSample],
    list[WeatherTrainingSample],
]:

    split_index = int(
        len(samples) * train_ratio
    )

    train_samples = samples[:split_index]
    test_samples = samples[split_index:]

    return train_samples, test_samples