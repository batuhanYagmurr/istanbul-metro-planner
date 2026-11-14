-- One month of IBB hourly public transport data -> rail boardings per
-- line, station, date and hour.
-- {csv_path} is filled in by metro/prep.py; every column is read as text and cast here.
SELECT
    CAST(transition_date AS DATE)                                  AS date,
    CAST(transition_hour AS INTEGER)                               AS hour,
    trim(line_name)                                                AS line,
    coalesce(nullif(upper(trim(station_poi_desc_cd)), ''), 'UNKNOWN') AS station,
    CAST(sum(CAST(number_of_passage AS BIGINT)) AS BIGINT)         AS boardings,
    CAST(sum(CAST(number_of_passenger AS BIGINT)) AS BIGINT)       AS passengers,
    CAST(sum(CASE WHEN product_kind = 'TAM'
                  THEN CAST(number_of_passage AS BIGINT) ELSE 0 END) AS BIGINT) AS b_full,
    CAST(sum(CASE WHEN product_kind LIKE 'INDIRIMLI%'
                  THEN CAST(number_of_passage AS BIGINT) ELSE 0 END) AS BIGINT) AS b_discount,
    CAST(sum(CASE WHEN product_kind = 'UCRETSIZ'
                  THEN CAST(number_of_passage AS BIGINT) ELSE 0 END) AS BIGINT) AS b_free,
    CAST(sum(CASE WHEN transfer_type = 'Aktarma'
                  THEN CAST(number_of_passage AS BIGINT) ELSE 0 END) AS BIGINT) AS b_transfer
FROM read_csv('{csv_path}', header = true, all_varchar = true)
WHERE road_type = 'RAYLI'
GROUP BY ALL
ORDER BY date, hour, line, station
