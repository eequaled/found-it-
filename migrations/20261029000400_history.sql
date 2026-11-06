-- migrate:up
CREATE TABLE report_status_history (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    report_id uuid NOT NULL REFERENCES reports(id),
    from_status report_status,
    to_status report_status NOT NULL,
    actor status_actor NOT NULL,
    note text CHECK (char_length(note) BETWEEN 1 AND 1000 AND note ~ '[^[:space:]]'),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CHECK (from_status IS NULL OR from_status <> to_status)
);
CREATE UNIQUE INDEX report_history_one_initial ON report_status_history(report_id) WHERE from_status IS NULL;
CREATE INDEX report_history_timeline ON report_status_history(report_id, id);

CREATE TABLE claim_status_history (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    claim_id uuid NOT NULL REFERENCES claims(id),
    from_status claim_status,
    to_status claim_status NOT NULL,
    actor status_actor NOT NULL,
    note text CHECK (char_length(note) BETWEEN 1 AND 1000 AND note ~ '[^[:space:]]'),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CHECK (from_status IS NULL OR from_status <> to_status)
);
CREATE UNIQUE INDEX claim_history_one_initial ON claim_status_history(claim_id) WHERE from_status IS NULL;
CREATE INDEX claim_history_timeline ON claim_status_history(claim_id, id);

-- migrate:down
DROP TABLE claim_status_history;
DROP TABLE report_status_history;
