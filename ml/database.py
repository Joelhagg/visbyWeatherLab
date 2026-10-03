import psycopg

from models import WeatherObservation
from training import ModelResult


def get_connection():
    return psycopg.connect(
        host="localhost",
        port=5432,
        dbname="visby_weather",
        user="postgres",
        password="Banan123456",
    )


def get_station_id(
    cursor,
    smhi_station_id: int,
) -> int:

    cursor.execute(
        """
        SELECT id
        FROM stations
        WHERE smhi_station_id = %s;
        """,
        (smhi_station_id,),
    )

    result = cursor.fetchone()

    if result is None:
        raise ValueError(
            f"SMHI-station {smhi_station_id} "
            "finns inte i databasen."
        )

    return result[0]


def get_parameter_id(
    cursor,
    smhi_parameter_id: int,
) -> int:

    cursor.execute(
        """
        SELECT id
        FROM parameters
        WHERE smhi_parameter_id = %s;
        """,
        (smhi_parameter_id,),
    )

    result = cursor.fetchone()

    if result is None:
        raise ValueError(
            f"SMHI-parameter {smhi_parameter_id} "
            "finns inte i databasen."
        )

    return result[0]


def get_observations(
    cursor,
    station_id: int,
    parameter_id: int,
) -> list[WeatherObservation]:

    cursor.execute(
        """
        SELECT
            timestamp,
            value,
            quality
        FROM observations
        WHERE station_id = %s
          AND parameter_id = %s
        ORDER BY timestamp;
        """,
        (
            station_id,
            parameter_id,
        ),
    )

    rows = cursor.fetchall()

    return [
        WeatherObservation(
            timestamp=row[0],
            value=row[1],
            quality=row[2],
        )
        for row in rows
    ]


def save_observations(
    cursor,
    station_id: int,
    parameter_id: int,
    observations,
    batch_size: int = 5000,
):
    total = len(observations)

    for start in range(0, total, batch_size):

        batch = observations[
            start:start + batch_size
        ]

        cursor.executemany(
            """
            INSERT INTO observations (
                station_id,
                parameter_id,
                timestamp,
                value,
                quality
            )
            VALUES (
                %s,
                %s,
                %s,
                %s,
                %s
            )
            ON CONFLICT (
                station_id,
                parameter_id,
                timestamp
            )
            DO NOTHING;
            """,
            [
                (
                    station_id,
                    parameter_id,
                    observation.timestamp,
                    observation.value,
                    observation.quality,
                )
                for observation in batch
            ],
        )

        processed = min(
            start + batch_size,
            total,
        )

        print(
            f"Sparat {processed:,} / {total:,} "
            f"observationer."
        )


def save_model_result(
        model_result: ModelResult,
) -> None:
    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO model_results (
                    trained_at,
                    mae,
                    training_samples,
                    features
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    %s
                )
                """,
                (
                    model_result.trained_at,
                    model_result.mae,
                    model_result.training_samples,
                    model_result.features,
                )
            )
        connection.commit()
    finally:
        connection.close()