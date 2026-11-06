-- migrate:up
CREATE INDEX reports_search_gin ON reports USING gin (search_vector)
    WHERE status = 'open';
CREATE INDEX reports_location_trgm ON reports USING gin (location_text gin_trgm_ops)
    WHERE status = 'open';
CREATE INDEX reports_public_order ON reports (created_at DESC, id DESC)
    WHERE status = 'open';

-- migrate:down
DROP INDEX reports_public_order;
DROP INDEX reports_location_trgm;
DROP INDEX reports_search_gin;
