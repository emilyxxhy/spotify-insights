WITH month_artist AS (
SELECT strftime('%Y-%m', endTime) AS month, artistName, SUM(msPlayed) AS ms_month_artist
FROM listens GROUP BY month, artistName),
month_total AS (SELECT month, SUM(ms_month_artist) AS ms_month_total FROM month_artist GROUP BY month)
SELECT m.month, m.artistName, ROUND(100.0 * m.ms_month_artist / t.ms_month_total, 1) AS month_share_pct
FROM month_artist m JOIN month_total t USING(month)
WHERE m.ms_month_artist >= 30*60*1000
ORDER BY m.month, month_share_pct DESC;