-- name: SearchPublicReports :many
WITH filtered AS (
    SELECT id, type, category, title, description, event_date, location_text, created_at,
        CASE WHEN sqlc.narg(q)::text IS NULL THEN 0::real
             ELSE ts_rank(search_vector, websearch_to_tsquery('simple', sqlc.narg(q)::text)) END AS rank
    FROM reports
    WHERE status = 'open'
      AND (sqlc.narg(q)::text IS NULL OR search_vector @@ websearch_to_tsquery('simple', sqlc.narg(q)::text))
      AND (sqlc.narg(type)::report_type IS NULL OR type = sqlc.narg(type)::report_type)
      AND (sqlc.narg(category)::report_category IS NULL OR category = sqlc.narg(category)::report_category)
      AND (sqlc.narg(date_from)::date IS NULL OR event_date >= sqlc.narg(date_from)::date)
      AND (sqlc.narg(date_to)::date IS NULL OR event_date <= sqlc.narg(date_to)::date)
      AND (sqlc.narg(location_pattern)::text IS NULL OR location_text ILIKE sqlc.narg(location_pattern)::text ESCAPE '\')
), totals AS (
    SELECT count(*) AS total FROM filtered
)
-- Text projections avoid the plugin constructing enums from a NULL sentinel.
SELECT totals.total, page.id, page.type::text AS type, page.category::text AS category, page.title, page.description,
       page.event_date, page.location_text, page.created_at
FROM totals
LEFT JOIN LATERAL (
    SELECT * FROM filtered
    ORDER BY rank DESC, created_at DESC, id DESC
    LIMIT sqlc.arg(page_size)::int OFFSET sqlc.arg(page_offset)::int
) AS page ON true
ORDER BY page.rank DESC, page.created_at DESC, page.id DESC;
