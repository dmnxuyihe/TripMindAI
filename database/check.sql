-- psql -U postgres -d travel_agent -f database/check.sql
SELECT COUNT(*) AS attractions FROM attractions;
SELECT city,COUNT(*) AS attraction_count FROM attractions GROUP BY city ORDER BY city;
SELECT COUNT(*) AS conversations FROM conversations;
SELECT COUNT(*) AS recorded_defects FROM defects;
