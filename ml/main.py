import requests
import csv

from dataclasses import dataclass
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from io import StringIO


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


def get_noon_observations(data: dict) -> list[WeatherObservation]:
    observations = data["value"]

    noon_observations = []

    for observation in observations:
        timestamp = datetime.fromtimestamp(
            observation["date"] / 1000,
            timezone.utc
        )

        local_time = timestamp.astimezone(STOCKHOLM_TIMEZONE)

        if local_time.hour == 12 and local_time.minute == 0:
            weather_observation = WeatherObservation(
                timestamp=local_time,
                temperature=float(observation["value"]),
                quality=observation["quality"],
            )

            noon_observations.append(weather_observation)

    return noon_observations

def get_noon_observation_from_archive(
        observations: list[WeatherObservation]
) -> list[WeatherObservation]:

    noon_observations = []

    for observation in observations:
        if observation.timestamp.hour == 12 and observation.timestamp.minute == 0:
            noon_observations.append(observation)

    return noon_observations


def get_temperature_for_date(
    observations: list[WeatherObservation],
    target_date
) -> float | None:

    for observation in observations:
        if observation.timestamp.date() == target_date:
            return observation.temperature

    return None

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

def get_approximate_observation(
        observations: list[WeatherObservation],
) -> list[WeatherObservation]:

    return [
        observation 
        for observation in observations
        if observation.quality == "G"
    ]

def count_quality(
    observations: list[WeatherObservation]
) -> dict[str, int]:
    quality_counts = {}

    for observation in observations:
        quality = observation.quality

        if quality not in quality_counts:
            quality_counts[quality] = 0

        quality_counts[quality] += 1

    return quality_counts


def main():
    print("Visby Weather Lab Started!")

    data = fetch_weather_data(SMHI_URL)

    noon_observations = get_noon_observations(data)

    print(
        f"Antal 12:00-observationer: "
        f"{len(noon_observations)}"
    )

    if noon_observations:
        print(
            f"Första observationen: "
            f"{noon_observations[0]}"
        )

    today = datetime.now(STOCKHOLM_TIMEZONE).date()

    historical_average = get_historical_average(
        noon_observations,
        today
    )

    print(
        f"Historiskt medel för " 
        f"{today}: kl 12:00: "
        f"{historical_average} °C"
    )

    target_date = datetime(2026, 4, 28).date()

    temperature = get_temperature_for_date(
        noon_observations,
        target_date
    )

    print(
        f"Temperatur {target_date} kl. 12:00: "
        f"{temperature} °C"
    )


    archive = fetch_weather_archive(
        SMHI_ARCHIVE_URL
    )

    archive_observations = parse_weather_archive(
        archive
    )

    print(
        f"Antal historiska observationer: "
        f"{len(archive_observations)}"
    )

    print(
        f"Första historiska observationen: "
        f"{archive_observations[0]}"
    )

    print(
        f"Sista historiska observationen: "
        f"{archive_observations[-1]}"
    )

    archive_noon_observations = get_noon_observation_from_archive(
        archive_observations
    )

    print(
        f"Antal historiska 12:00-observationer: "
        f"{len(archive_noon_observations)}"
    )

    print(
        f"Första historiska 12:00-observationen: "
        f"{archive_noon_observations[0]}"
    )
    
    print(
        f"Sista historiska 12:00-observationen: "
        f"{archive_noon_observations[-1]}"
    )

    approved_noon_observations = get_approximate_observation(
        archive_noon_observations
    )

    print(
        f"Godkända historiska 12:00-observationer: "
        f"{len(approved_noon_observations)}"
    )


    quality_counts = count_quality(
        archive_noon_observations
    )

    print("Kvalitetsfördelning:")

    for quality, count in quality_counts.items():
        print(f"{quality}: {count}")

    


if __name__ == "__main__":
    main()