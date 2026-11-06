-- name: FindMatchCandidates :many
WITH source AS (
    SELECT original.type, original.category, original.event_date,
           original.title, original.description, original.location_text
    FROM reports AS original WHERE original.id = sqlc.arg(report_id) AND original.status = 'open'
)
-- Text projections avoid enum decoding from NULL for an empty candidate list.
SELECT candidate.id, candidate.type::text AS type, candidate.category::text AS category,
       candidate.title, candidate.description, candidate.event_date,
       candidate.location_text, candidate.created_at
FROM source
LEFT JOIN LATERAL (
    SELECT r.id, r.type, r.category, r.title, r.description,
           r.event_date, r.location_text, r.created_at,
           similarity(r.title || ' ' || r.description, source.title || ' ' || source.description)
           + similarity(r.location_text, source.location_text)
           + 0.1::real / (1 + abs(r.event_date - source.event_date)) AS score
    FROM reports AS r
    WHERE r.status = 'open'
      AND r.type = CASE WHEN source.type = 'lost' THEN 'found'::report_type ELSE 'lost'::report_type END
      AND r.category = source.category
      AND r.event_date BETWEEN source.event_date - sqlc.arg(window_days)::int
                           AND source.event_date + sqlc.arg(window_days)::int
    ORDER BY score DESC, r.created_at DESC, r.id DESC
    LIMIT 10
) AS candidate ON true
ORDER BY candidate.score DESC, candidate.created_at DESC, candidate.id DESC;
