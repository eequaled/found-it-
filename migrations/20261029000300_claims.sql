-- migrate:up
CREATE TABLE claims (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    report_id uuid NOT NULL,
    report_type report_type NOT NULL DEFAULT 'found' CHECK (report_type = 'found'),
    status claim_status NOT NULL DEFAULT 'pending',
    claimant_name text NOT NULL CHECK (char_length(claimant_name) BETWEEN 1 AND 100 AND claimant_name ~ '[^[:space:]]'),
    claimant_contact text NOT NULL CHECK (char_length(claimant_contact) BETWEEN 3 AND 254 AND claimant_contact ~ '[^[:space:]]'),
    evidence text NOT NULL CHECK (char_length(evidence) BETWEEN 10 AND 5000 AND evidence ~ '[^[:space:]]'),
    tracking_token_hash bytea NOT NULL UNIQUE CHECK (octet_length(tracking_token_hash) = 32),
    decision_note text CHECK (char_length(decision_note) BETWEEN 1 AND 1000 AND decision_note ~ '[^[:space:]]'),
    decided_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (report_id, report_type) REFERENCES reports (id, type),
    CHECK ((status = 'pending') = (decided_at IS NULL)),
    CHECK (status <> 'pending' OR decision_note IS NULL),
    CHECK (status <> 'rejected' OR decision_note IS NOT NULL)
);
CREATE UNIQUE INDEX claims_one_approved_per_report ON claims (report_id) WHERE status = 'approved';

-- migrate:down
DROP TABLE claims;
