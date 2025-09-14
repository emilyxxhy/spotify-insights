SELECT CASE strftime('%w', endTime)
WHEN '0' THEN 'Sun' WHEN '1' THEN 'Mon' WHEN '2' THEN 'Tue' WHEN '3' THEN 'Wed' WHEN '4' THEN 'Thu' WHEN '5' THEN 'Fri' WHEN '6' THEN 'Sat' END AS weekday,
ROUND(SUM(msPlayed)/3600000.0, 2) AS hours_listened
FROM listens GROUP BY strftime('%w', endTime) ORDER BY strftime('%w', endTime);