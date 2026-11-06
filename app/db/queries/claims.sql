-- name: LockReportForClaim :one
SELECT id, type, status FROM reports WHERE id = sqlc.arg(id) FOR SHARE;

-- name: InsertClaim :one
INSERT INTO claims (report_id, claimant_name, claimant_contact, evidence, tracking_token_hash)
VALUES (sqlc.arg(report_id), sqlc.arg(claimant_name), sqlc.arg(claimant_contact),
        sqlc.arg(evidence), sqlc.arg(tracking_token_hash))
RETURNING id;
