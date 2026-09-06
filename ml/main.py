import csv

import requests

from dataclasses import dataclass
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo


SMHI_URL = (
    "https://opendata-download-metobs.smhi.se/"
    "api/version/1.0/"
    "parameter/1/"
    "station/78400/"
    "period/latest-months/"
    "data.json"
)

SMHI_ARCHIVE_URL = (
    "https://opendata-download-metobs.smhi.se/"
    "api/version/1.0/"
    "parameter/1/"
    "station/78400/"
    "period/corrected-archive/"
    "data.csv"
)

STOCKHOLM_TIMEZONE = ZoneInfo("Europe/Stockholm")


@dataclass
class WeatherObservation:
    timestamp: datetime
    temperature: float
    quality: str


def fetch_weather_data(url: str) -> dict:
    response = requests.get(url)
    response.raise_for_status()

    return response.json()


def fetch_weather_archive(url: str) -> str:
    response = requests.get(url)
    response.raise_for_status()

    return response.text


def parse_weather_archive(
    csv_data: str
) -> list[WeatherObservation]:

    observations = []

    lines = csv_data.splitlines()

    data_start = None

    for index, line in enumerate(lines):
        if line.startswith(
            "Datum;Tid (UTC);Lufttemperatur;Kvalitet"
        ):
            data_start = index
            break

    if data_start is None:
        raise ValueError(
            "Kunde inte hitta CSV-datan i SMHI-svaret."
        )

    data_lines = lines[data_start:]

    reader = csv.DictReader(
        data_lines,
        delimiter=";"
    )

    for row in reader:
        if not row["Datum"]:
            continue

        timestamp = datetime.strptime(
            f'{row["Datum"]} {row["Tid (UTC)"]}',
            "%Y-%m-%d %H:%M:%S"
        )

        timestamp = timestamp.replace(
            tzinfo=timezone.utc
        )

        local_time = timestamp.astimezone(
            STOCKHOLM_TIMEZONE
        )

        observation = WeatherObservation(
            timestamp=local_time,
            temperature=float(
                row["Lufttemperatur"]
            ),
            quality=row["Kvalitet"],
        )

        observations.append(observation)

    return observations


def get_midday_observation(
    observations: list[WeatherObservation],
    target_date
) -> WeatherObservation | None:

    preferred_hours = [12, 13, 14]

    for hour in preferred_hours:
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
        list[WeatherObservation]
    ] = {}

    for observation in observations:
        observation_date = observation.timestamp.date()
        if observation_date not in observations_by_date:
            observations_by_date[observation_date] = []
        observations_by_date[observation_date].append(observation)

    midday_observations: list[WeatherObservation] = []
    for observation_date, daily_observations in observations_by_date.items():
        midday_observation = get_midday_observation(daily_observations, observation_date)
        if midday_observation:
            midday_observations.append(midday_observation)

    return midday_observations


def get_historical_average(
    observations: list[WeatherObservation],
    target_date
) -> float | None:

    temperatures = []

    for observation in observations:
        observation_date = observation.timestamp.date()

        if (
            observation_date.month == target_date.month
            and observation_date.day == target_date.day
        ):
            temperatures.append(observation.temperature)

    if not temperatures:
        return None

    return sum(temperatures) / len(temperatures)

def get_historical_average_before_date(
    observations: list[WeatherObservation],
    target_date: date
) -> float | None:

    temperatures = []

    for observation in observations:
        observation_date = observation.timestamp.date()

        if (
            observation_date.month == target_date.month
            and observation_date.day == target_date.day
            and observation_date < target_date
        ):
            temperatures.append(observation.temperature)

    if not temperatures:
        return None

    return sum(temperatures) / len(temperatures)

def calculate_baseline_mae(
    observations: list[WeatherObservation],
    start_year: int,
    end_year: int
) -> float | None:

    errors = []

    for year in range(start_year, end_year + 1):

        for observation in observations:

            target_date = observation.timestamp.date()

            if target_date.year != year:
                continue

            prediction = get_historical_average_before_date(
                observations,
                target_date
            )

            if prediction is None:
                continue

            error = abs(
                prediction - observation.temperature
            )

            errors.append(error)

    if not errors:
        return None

    return sum(errors) / len(errors)


def main():
    print("Visby Weather Lab Started!")

    archive = fetch_weather_archive(
        SMHI_ARCHIVE_URL
    )

    observations = parse_weather_archive(
        archive
    )

    print(
        f"Antal historiska observationer: "
        f"{len(observations)}"
    )

    today = datetime.now(
        STOCKHOLM_TIMEZONE
    ).date()

    midday_observation = get_midday_observation(
        observations,
        today
    )

    if midday_observation:
        print(
            f"Temperatur mitt på dagen "
            f"{today}: "
            f"{midday_observation.temperature} °C "
            f"({midday_observation.timestamp.strftime('%H:%M')})"
        )
    else:
        print(
            f"Ingen observation mitt på dagen "
            f"hittades för {today}."
        )


    midday_observations = get_midday_observations(
        observations
    )

    historical_average = get_historical_average(
        midday_observations,
        today
    )

    print(
        f"Historiskt medel för "
        f"{today}: "
        f"{historical_average} °C"
    )

    print(
        f"Antal dagar med mitt-på-dagen-observation: "
        f"{len(midday_observations)}"
    )

    print(
        f"Första observationen: "
        f"{midday_observations[0]}"
    )

    print(
        f"Sista observationen: "
        f"{midday_observations[-1]}"
    )

    test_date = date(2020, 9, 6)

    prediction = get_historical_average_before_date(
        midday_observations,
        test_date
    )

    actual = get_midday_observation(
        midday_observations,
        test_date
    )

    print(
        f"\nTestdatum: {test_date}"
    )

    print(
        f"Historiskt medel: {prediction:.2f} °C"
    )

    print(
        f"Faktisk temperatur: "
        f"{actual.temperature:.2f} °C"
    )

    baseline_mae = calculate_baseline_mae(
        midday_observations,
        2010,
        2020
    )

    print(
        f"Baseline MAE 2010-2020: "
        f"{baseline_mae:.2f} °C"
    )


if __name__ == "__main__":
    main()