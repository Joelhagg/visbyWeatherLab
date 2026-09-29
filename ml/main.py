import csv
import requests

from dataclasses import dataclass
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from database import (
    get_connection,
    get_station_id,
    get_parameter_id,
    save_observation
)

VISBY_AIRPORT = 78400

SMHI_AIR_TEMPERATURE = 1
SMHI_WIND_SPEED = 4

STOCKHOLM_TIMEZONE = ZoneInfo("Europe/Stockholm")

SMHI_BASE_URL = (
    "https://opendata-download-metobs.smhi.se/"
    "api/version/1.0"
)

SMHI_LATEST_URL = (
    "https://opendata-download-metobs.smhi.se/"
    "api/version/latest.json"
)

@dataclass
class WeatherObservation:
    timestamp: datetime
    value: float
    quality: str


def build_smhi_archive_url(
    parameter_id: int,
    station_id: int,
) -> str:
    return (
        f"{SMHI_BASE_URL}/"
        f"parameter/{parameter_id}/"
        f"station/{station_id}/"
        "period/corrected-archive/"
        "data.csv"
    )


def fetch_weather_archive(url: str) -> str:
    response = requests.get(url)
    response.raise_for_status()

    return response.text


def fetch_smhi_parameter(
    parameter_id: int,
    station_id: int,
    period: str = "latest-months",
) -> dict:
    url = (
        f"{SMHI_BASE_URL}/"
        f"parameter/{parameter_id}/"
        f"station/{station_id}/"
        f"period/{period}/"
        "data.json"
    )

    response = requests.get(url)
    response.raise_for_status()

    return response.json()


def fetch_smhi_catalog() -> dict:
    response = requests.get(SMHI_LATEST_URL)
    response.raise_for_status()

    return response.json()


def parse_weather_archive(
    csv_data: str,
    value_column: str,
) -> list[WeatherObservation]:

    observations = []

    lines = csv_data.splitlines()

    data_start = None

    for index, line in enumerate(lines):
        if line.startswith(
            f"Datum;Tid (UTC);{value_column};Kvalitet"
        ):
            data_start = index
            break

    if data_start is None:
        raise ValueError(
            f"Kunde inte hitta CSV-data för '{value_column}'."
        )

    data_lines = lines[data_start:]

    reader = csv.DictReader(
        data_lines,
        delimiter=";",
    )

    for row in reader:
        if not row["Datum"]:
            continue

        timestamp = datetime.strptime(
            f'{row["Datum"]} {row["Tid (UTC)"]}',
            "%Y-%m-%d %H:%M:%S",
        )

        timestamp = timestamp.replace(
            tzinfo=timezone.utc,
        )

        local_time = timestamp.astimezone(
            STOCKHOLM_TIMEZONE,
        )

        observations.append(
            WeatherObservation(
                timestamp=local_time,
                value=float(row[value_column]),
                quality=row["Kvalitet"],
            )
        )

    return observations


def get_midday_observation(
    observations: list[WeatherObservation],
    target_date: date,
) -> WeatherObservation | None:

    # Our definition of "midday":
    # 12:00 is preferred, 13:00 is fallback.
    preferred_hours = [12, 13]

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


def get_historical_average(
    observations: list[WeatherObservation],
    target_date: date,
) -> float | None:

    temperatures = [
        observation.value
        for observation in observations
        if (
            observation.timestamp.date().month
            == target_date.month
            and observation.timestamp.date().day
            == target_date.day
        )
    ]

    if not temperatures:
        return None

    return sum(temperatures) / len(temperatures)


def get_historical_average_before_date(
    observations: list[WeatherObservation],
    target_date: date,
) -> float | None:

    temperatures = [
        observation.value
        for observation in observations
        if (
            observation.timestamp.date().month
            == target_date.month
            and observation.timestamp.date().day
            == target_date.day
            and observation.timestamp.date()
            < target_date
        )
    ]

    if not temperatures:
        return None

    return sum(temperatures) / len(temperatures)


def calculate_baseline_mae(
    observations: list[WeatherObservation],
    start_year: int,
    end_year: int,
) -> float | None:

    errors = []

    for year in range(start_year, end_year + 1):
        for observation in observations:

            target_date = observation.timestamp.date()

            if target_date.year != year:
                continue

            prediction = get_historical_average_before_date(
                observations,
                target_date,
            )

            if prediction is None:
                continue

            errors.append(
                abs(prediction - observation.value)
            )

    if not errors:
        return None

    return sum(errors) / len(errors)


def main() -> None:
    print("Visby Weather Lab Started!")

    connection = get_connection()
    cursor = connection.cursor()

    database_station_id = get_station_id(
        cursor,
        VISBY_AIRPORT,
    )

    database_temperature_parameter_id = get_parameter_id(
        cursor,
        SMHI_AIR_TEMPERATURE,
    )

    print(
        f"Database station ID: "
        f"{database_station_id}"
    )

    print(
        f"Database temperature parameter ID: "
        f"{database_temperature_parameter_id}"
    )

    # --------------------------------------------------
    # TEMPERATURE
    # --------------------------------------------------

    temperature_url = build_smhi_archive_url(
        parameter_id = SMHI_AIR_TEMPERATURE,
        station_id=VISBY_AIRPORT,
    )

    temperature_archive = fetch_weather_archive(
        temperature_url,
    )

    temperature_observations = parse_weather_archive(
        temperature_archive,
        "Lufttemperatur",
    )

    print(
        f"Antal historiska temperaturobservationer: "
        f"{len(temperature_observations)}"
    )

    if temperature_observations:

        observation = temperature_observations[0]

        saved = save_observation(
            cursor,
            database_station_id,
            database_temperature_parameter_id,
            observation
        )

        if saved:
            print("Observation sparad i PostgreSQL!")
        else:
            print("Observationen fanns redan.")

    today = datetime.now(
        STOCKHOLM_TIMEZONE
    ).date()

    midday_temperature_observations = (
        get_midday_observations(
            temperature_observations,
        )
    )

    today_midday = get_midday_observation(
        midday_temperature_observations,
        today,
    )

    if today_midday:
        print(
            f"Temperatur mitt på dagen "
            f"{today}: "
            f"{today_midday.value:.2f} °C "
            f"({today_midday.timestamp.strftime('%H:%M')})"
        )
    else:
        print(
            f"Ingen observation mitt på dagen "
            f"hittades för {today}."
        )

    historical_average = get_historical_average(
        midday_temperature_observations,
        today,
    )

    if historical_average is not None:
        print(
            f"Historiskt medel för "
            f"{today}: "
            f"{historical_average:.2f} °C"
        )

    print(
        f"Antal dagar med mitt-på-dagen-observation: "
        f"{len(midday_temperature_observations)}"
    )

    # --------------------------------------------------
    # WIND
    # --------------------------------------------------

    wind_url = build_smhi_archive_url(
        parameter_id=4,
        station_id=VISBY_AIRPORT,
    )

    wind_archive = fetch_weather_archive(
        wind_url,
    )

    wind_observations = parse_weather_archive(
        wind_archive,
        "Vindhastighet",
    )

    print(
        f"Antal historiska vindobservationer: "
        f"{len(wind_observations)}"
    )

    if wind_observations:
        first_wind_observation = wind_observations[0]

        print(
            f"Första vindobservationen: "
            f"{first_wind_observation.timestamp} - "
            f"{first_wind_observation.value:.2f} m/s "
            f"({first_wind_observation.quality})"
        )

    connection.commit()

    cursor.close()
    connection.close()


if __name__ == "__main__":
    main()