import psycopg


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


def save_observation(
    cursor,
    station_id: int,
    parameter_id: int,
    observation,
) -> bool:

    cursor.execute(
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
        (
            station_id,
            parameter_id,
            observation.timestamp,
            observation.value,
            observation.quality,
        ),
    )

    return cursor.rowcount == 1


def main():
    connection = get_connection()

    print("Ansluten till PostgreSQL!")

    cursor = connection.cursor()

    station_id = get_station_id(
        cursor,
        78400,
    )

    parameter_id = get_parameter_id(
        cursor,
        1,
    )

    print(f"Databas station_id: {station_id}")
    print(f"Databas parameter_id: {parameter_id}")

    connection.commit()

    cursor.close()
    connection.close()


if __name__ == "__main__":
    main()