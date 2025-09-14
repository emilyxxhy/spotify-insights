SELECT trackName, artistName, ROUND(SUM(msPlayed)/3600000.0, 2) AS hours_listened, COUNT(*) AS plays
FROM listens GROUP BY trackName, artistName ORDER BY hours_listened DESC, plays DESC LIMIT 25;