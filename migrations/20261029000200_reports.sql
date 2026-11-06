-- migrate:up
CREATE TABLE reports (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    type report_type NOT NULL,
    status report_status NOT NULL DEFAULT 'pending_review',
    category report_category NOT NULL,
    title text NOT NULL CHECK (char_length(title) BETWEEN 3 AND 120 AND title ~ '[^[:space:]]'),
    description text NOT NULL CHECK (char_length(description) BETWEEN 10 AND 5000 AND description ~ '[^[:space:]]'),
    event_date date NOT NULL,
    location_text text NOT NULL CHECK (char_length(location_text) BETWEEN 2 AND 200 AND location_text ~ '[^[:space:]]'),
    photo_path text CHECK (photo_path ~ '^[a-f0-9]{32}\.(jpg|png|webp)$'),
    contact_name text CHECK (char_length(contact_name) BETWEEN 1 AND 100 AND contact_name ~ '[^[:space:]]'),
    contact_email text CHECK (char_length(contact_email) BETWEEN 3 AND 254 AND contact_email ~ '[^[:space:]]'),
    contact_phone text CHECK (char_length(contact_phone) BETWEEN 3 AND 40 AND contact_phone ~ '[^[:space:]]'),
    tracking_token_hash bytea NOT NULL UNIQUE CHECK (octet_length(tracking_token_hash) = 32),
    search_vector tsvector GENERATED ALWAYS AS (
        setweight(to_tsvector('simple'::regconfig, title), 'A') ||
        setweight(to_tsvector('simple'::regconfig, description), 'B')
    ) STORED,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (id, type)
);

-- migrate:down
DROP TABLE reports;
