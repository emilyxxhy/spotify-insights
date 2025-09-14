SELECT strftime('%Y-%m', endTime) AS month, ROUND(SUM(msPlayed)/3600000.0, 2) AS hours_listened,
COUNT(DISTINCT artistName) AS unique_artists, COUNT(DISTINCT trackName) AS unique_tracks
FROM listens GROUP BY month ORDER BY month;