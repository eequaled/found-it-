-- migrate:up
CREATE INDEX reports_match_candidates ON reports (type, category, event_date)
    WHERE status = 'open';

-- migrate:down
DROP INDEX reports_match_candidates;
