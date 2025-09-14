WITH first_seen AS (SELECT artistName, MIN(date(endTime)) AS first_date FROM listens GROUP BY artistName),
calendar AS (SELECT DISTINCT date(endTime) AS d FROM listens),
daily AS (SELECT c.d, COALESCE(SUM(CASE WHEN f.first_date = c.d THEN 1 ELSE 0 END),0) AS new_artists FROM calendar c LEFT JOIN first_seen f ON f.first_date = c.d GROUP BY c.d)
SELECT d AS date, new_artists, SUM(new_artists) OVER (ORDER BY d ROWS UNBOUNDED PRECEDING) AS cumulative_artists FROM daily ORDER BY date;