SELECT CAST(strftime('%H', endTime) AS INTEGER) AS hour, ROUND(SUM(msPlayed)/3600000.0, 2) AS hours_listened
FROM listens GROUP BY hour ORDER BY hour;