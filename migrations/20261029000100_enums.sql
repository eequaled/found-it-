-- migrate:up
CREATE EXTENSION pg_trgm;
CREATE TYPE report_type AS ENUM ('lost', 'found');
CREATE TYPE report_status AS ENUM ('pending_review', 'open', 'resolved', 'rejected', 'removed');
CREATE TYPE claim_status AS ENUM ('pending', 'approved', 'rejected', 'withdrawn');
CREATE TYPE report_category AS ENUM ('phone', 'wallet', 'keys', 'bag', 'documents', 'clothing', 'other');
CREATE TYPE status_actor AS ENUM ('system', 'owner', 'admin');

-- migrate:down
DROP TYPE status_actor;
DROP TYPE report_category;
DROP TYPE claim_status;
DROP TYPE report_status;
DROP TYPE report_type;
DROP EXTENSION pg_trgm;
