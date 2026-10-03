from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

import csv
import requests

from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error

from database import (
    get_connection,
    get_station_id,
    get_parameter_id,
    get_observations,
    save_observations,
    save_model_result,
)

from models import WeatherObservation

from training import(
    ModelResult,
    build_training_samples,
    build_features,
    build_targets,
    split_training_data,
    get_midday_observation,
    get_midday_observations,
) 


VISBY_AIRPORT = 78400

SMHI_AIR_TEMPERATURE = 1
SMHI_WIND_SPEED = 4

STOCKHOLM_TIMEZONE = ZoneInfo("Europe/Stockholm")

SMHI_BASE_URL = (
    "https://opendata-download-metobs.smhi.se/"
    "api/version/1.0"
)


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
            f"Kunde inte hitta CSV-data "
            f"för '{value_column}'."
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
                abs(
                    prediction - observation.value
                )
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

    database_temperature_parameter_id = (
        get_parameter_id(
            cursor,
            SMHI_AIR_TEMPERATURE,
        )
    )

    temperature_observations = get_observations(
        cursor,
        database_station_id,
        database_temperature_parameter_id,
    )

    training_samples = build_training_samples(
        temperature_observations
    )

    print(
        f"Antal training samples: "
        f"{len(training_samples)}"
    )

    print(
        f"Första training sample: "
        f"{training_samples[0]}"
    )

    print(
        f"Antal temperatur-observationer "
        f"från PostgreSQL: "
        f"{len(temperature_observations)}"
    )

    train_samples, test_samples = split_training_data(
        training_samples
    )

    X_train = build_features(train_samples)
    y_train = build_targets(train_samples)

    X_test = build_features(test_samples)
    y_test = build_targets(test_samples)

    model = LinearRegression()

    model.fit(
        X_train,
        y_train,
    )

    print("Coefficients:", model.coef_)
    print("Intercept:", model.intercept_)

    predictions = model.predict(
        X_test
    )

    mae = mean_absolute_error(
        y_test,
        predictions,
    )

    print(
        f"Linear Regression MAE: "
        f"{mae:.2f} °C"
    )

    model_result = ModelResult(
        trained_at=datetime.now(),
        mae=mae,
        training_samples=len(X_train),
        features=[
            "sin_day_of_year",
            "cos_day_of_year",
            "previous_temperature",
        ],
    )

    save_model_result(
        model_result
    )

    print("Model Result:")
    print(model_result)

    for index in range(5):

        print(
            f"Prediction: "
            f"{predictions[index]:.2f} °C | "
            f"Actual: "
            f"{y_test[index]:.2f} °C"
        )

    print(
        f"Antal training samples: "
        f"{len(train_samples)}"
    )

    print(
        f"Antal test samples: "
        f"{len(test_samples)}"
    )

    print(
        f"Första training sample: "
        f"{train_samples[0]}"
    )

    print(
        f"Första test sample: "
        f"{test_samples[0]}"
    )

    features = build_features(
        training_samples
    )

    targets = build_targets(
        training_samples
    )

    print(
        f"Första features: "
        f"{features[0]}"
    )

    print(
        f"Första target: "
        f"{targets[0]}"
    )

    if temperature_observations:

        print(
            f"Första observationen: "
            f"{temperature_observations[0]}"
        )

    today = datetime.now(
        STOCKHOLM_TIMEZONE
    ).date()

    midday_observations = (
        get_midday_observations(
            temperature_observations,
        )
    )

    today_midday = get_midday_observation(
        midday_observations,
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

    historical_average = (
        get_historical_average(
            midday_observations,
            today,
        )
    )

    if historical_average is not None:

        print(
            f"Historiskt medel för "
            f"{today}: "
            f"{historical_average:.2f} °C"
        )

    print(
        f"Antal dagar med "
        f"mitt-på-dagen-observation: "
        f"{len(midday_observations)}"
    )

    cursor.close()
    connection.close()


if __name__ == "__main__":
    main()