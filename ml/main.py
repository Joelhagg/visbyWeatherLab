import csv

import requests

from dataclasses import dataclass
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo


VISBY_AIRPORT = 78400
STOCKHOLM_TIMEZONE = ZoneInfo("Europe/Stockholm")

SMHI_BASE_URL = (
    "https://opendata-download-metobs.smhi.se/"
    "api/version/1.0"
)

SMHI_LATEST_URL = (
    "https://opendata-download-metobs.smhi.se/"
    "api/version/latest.json"
)

SMHI_ARCHIVE_URL = (
    f"{SMHI_BASE_URL}/"
    "parameter/1/"
    f"station/{VISBY_AIRPORT}/"
    "period/corrected-archive/"
    "data.csv"
)

def build_smhi_archive_url(
    parameter_id: int,
    station_id: int
) -> str:

    return (
        f"{SMHI_BASE_URL}/"
        f"parameter/{parameter_id}/"
        f"station/{station_id}/"
        "period/corrected-archive/"
        "data.csv"
    )

@dataclass
class WeatherObservation:
    timestamp: datetime
    temperature: float
    quality: str


def fetch_weather_archive(url: str) -> str:
    response = requests.get(url)
    response.raise_for_status()

    return response.text


def fetch_smhi_parameter(
    parameter_id: int,
    station_id: int,
    period: str = "latest-months"
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


def inspect_smhi_parameter(
    parameter_id: int
) -> None:

    data = fetch_smhi_parameter(
        parameter_id=parameter_id,
        station_id=VISBY_AIRPORT
    )

    print()
    print("=" * 50)
    print(f"Parameter: {data['parameter']['name']}")
    print(f"ID: {data['parameter']['key']}")
    print(f"Enhet: {data['parameter']['unit']}")
    print(f"Beskrivning: {data['parameter']['summary']}")
    print(f"Station: {data['station']['name']}")
    print(f"Observationer: {len(data['value'])}")
    print("=" * 50)

def fetch_smhi_catalog() -> dict:
    response = requests.get(
        SMHI_LATEST_URL
    )
    response.raise_for_status()

    return response.json()


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
    target_date: date
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

        observations_by_date.setdefault(
            observation_date,
            []
        ).append(observation)

    midday_observations: list[WeatherObservation] = []

    for observation_date, daily_observations in observations_by_date.items():

        midday_observation = get_midday_observation(
            daily_observations,
            observation_date
        )

        if midday_observation:
            midday_observations.append(
                midday_observation
            )

    return midday_observations


def get_historical_average(
    observations: list[WeatherObservation],
    target_date: date
) -> float | None:

    temperatures = []

    for observation in observations:
        observation_date = observation.timestamp.date()

        if (
            observation_date.month == target_date.month
            and observation_date.day == target_date.day
        ):
            temperatures.append(
                observation.temperature
            )

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
            temperatures.append(
                observation.temperature
            )

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

def get_smhi_parameters(
    catalog: dict
) -> list[dict]:

    parameters = []

    for resource in catalog["resource"]:

        parameter_link = next(
            link["href"]
            for link in resource["link"]
            if link["rel"] == "parameter"
        )

        parameters.append({
            "id": int(resource["key"]),
            "name": resource["title"],
            "summary": resource["summary"],
            "unit": resource["unit"],
            "url": parameter_link,
        })

    return parameters

def print_smhi_parameters(
    catalog: dict
) -> None:

    parameters = get_smhi_parameters(catalog)

    print()
    print("Tillgängliga SMHI-parametrar:")
    print("-" * 100)

    for parameter in parameters:

        print(
            f'{parameter["id"]:>2} | '
            f'{parameter["name"]:<30} | '
            f'{parameter["summary"]:<55} | '
            f'{parameter["unit"]}'
        )

def inspect_smhi_parameter(
    parameter_id: int
) -> None:

    try:
        data = fetch_smhi_parameter(
            parameter_id=parameter_id,
            station_id=VISBY_AIRPORT
        )

    except requests.HTTPError as error:
        print()
        print("=" * 50)
        print(f"Parameter ID: {parameter_id}")
        print("Status: Ej tillgänglig")
        print(f"Fel: {error}")
        print("=" * 50)

        return

    print()
    print("=" * 50)
    print(f"Parameter: {data['parameter']['name']}")
    print(f"ID: {data['parameter']['key']}")
    print(f"Enhet: {data['parameter']['unit']}")
    print(f"Beskrivning: {data['parameter']['summary']}")
    print(f"Station: {data['station']['name']}")
    print(f"Observationer: {len(data['value'])}")
    print("=" * 50)

def fetch_weather_archive(url: str) -> str:
    response = requests.get(url)
    response.raise_for_status()

    return response.text

def inspect_smhi_archive(
    parameter_id: int,
    station_id: int
) -> None:

    url = build_smhi_archive_url(
        parameter_id=parameter_id,
        station_id=station_id
    )

    response = requests.get(url)
    response.raise_for_status()

    lines = response.text.splitlines()

    print()
    print("=" * 60)
    print(f"Parameter ID: {parameter_id}")
    print(f"Station ID: {station_id}")
    print("=" * 60)

    for line in lines[:12]:
        print(line)

def analyze_midday_coverage(
    observations: list[WeatherObservation]
) -> None:

    dates = set(
        observation.timestamp.date()
        for observation in observations
    )

    observations_12 = set()
    observations_13 = set()

    for observation in observations:

        if observation.timestamp.hour == 12:
            observations_12.add(
                observation.timestamp.date()
            )

        if observation.timestamp.hour == 13:
            observations_13.add(
                observation.timestamp.date()
            )

    total_days = len(dates)

    only_12 = len(
        dates & observations_12
    )

    twelve_or_thirteen = len(
        dates & (observations_12 | observations_13)
    )

    print()
    print("=" * 50)
    print("Mitt-på-dagen-täckning")
    print("=" * 50)

    print(
        f"Totalt antal dagar: "
        f"{total_days}"
    )

    print(
        f"12:00 finns: "
        f"{only_12}"
    )

    print(
        f"12:00 eller 13:00 finns: "
        f"{twelve_or_thirteen}"
    )

    print(
        f"Förlorade dagar om vi bara använder 12:00: "
        f"{total_days - only_12}"
    )

    print(
        f"Förlorade dagar med 12:00 → 13:00: "
        f"{total_days - twelve_or_thirteen}"
    )

    print("=" * 50)

def analyze_midday_coverage_by_year(
    observations: list[WeatherObservation]
) -> None:

    observations_by_year: dict[int, set[date]] = {}

    for observation in observations:

        year = observation.timestamp.year
        observation_date = observation.timestamp.date()

        observations_by_year.setdefault(
            year,
            set()
        ).add(observation_date)

    print()
    print("=" * 70)
    print("Mitt-på-dagen-täckning per år")
    print("=" * 70)

    print(
        f"{'År':<6}"
        f"{'Totalt':>10}"
        f"{'12:00':>10}"
        f"{'13:00':>10}"
        f"{'12→13':>10}"
        f"{'Saknas':>10}"
    )

    print("-" * 70)

    for year in sorted(observations_by_year):

        dates = observations_by_year[year]

        observations_12 = {
            observation.timestamp.date()
            for observation in observations
            if (
                observation.timestamp.year == year
                and observation.timestamp.hour == 12
            )
        }

        observations_13 = {
            observation.timestamp.date()
            for observation in observations
            if (
                observation.timestamp.year == year
                and observation.timestamp.hour == 13
            )
        }

        total_days = len(dates)

        only_12 = len(
            dates & observations_12
        )

        fallback = len(
            dates & (observations_12 | observations_13)
        )

        missing = (
            total_days - fallback
        )

        print(
            f"{year:<6}"
            f"{total_days:>10}"
            f"{only_12:>10}"
            f"{len(observations_13):>10}"
            f"{fallback:>10}"
            f"{missing:>10}"
        )

    print("=" * 70)


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

    inspect_smhi_parameter(1)
    inspect_smhi_parameter(4)
    inspect_smhi_parameter(3)
    inspect_smhi_parameter(6)
    inspect_smhi_parameter(9)
    inspect_smhi_parameter(7)
    inspect_smhi_parameter(16)
    inspect_smhi_parameter(10)
    inspect_smhi_parameter(21)
    inspect_smhi_parameter(39)

    catalog = fetch_smhi_catalog()

    print()
    print("SMHI API-katalog:")
    print_smhi_parameters(catalog)  

    archive_url = build_smhi_archive_url(
        parameter_id=4,
        station_id=VISBY_AIRPORT
    )

    archive = fetch_weather_archive(
        archive_url
    )

    wind_url = build_smhi_archive_url(
        parameter_id=4,
        station_id=VISBY_AIRPORT
    )

    print()
    print("Vindhastighetens arkiv-URL:")
    print(wind_url)

    wind_archive = fetch_weather_archive(
        wind_url
    )

    print()
    print("Första 20 raderna från vindarkivet:")
    print("\n".join(wind_archive.splitlines()[:20]))

    inspect_smhi_archive(1, VISBY_AIRPORT)
    inspect_smhi_archive(4, VISBY_AIRPORT)
    inspect_smhi_archive(6, VISBY_AIRPORT)
    inspect_smhi_archive(9, VISBY_AIRPORT)
    inspect_smhi_archive(7, VISBY_AIRPORT)
    inspect_smhi_archive(16, VISBY_AIRPORT)
    inspect_smhi_archive(21, VISBY_AIRPORT)
    inspect_smhi_archive(39, VISBY_AIRPORT)

    analyze_midday_coverage(
        observations
    )

    analyze_midday_coverage_by_year(
        observations
    )

if __name__ == "__main__":
    main()