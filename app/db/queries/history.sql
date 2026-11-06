-- name: InsertReportHistory :one
INSERT INTO report_status_history (report_id, from_status, to_status, actor, note)
VALUES (sqlc.arg(report_id), sqlc.narg(from_status)::report_status,
        sqlc.arg(to_status)::report_status, sqlc.arg(actor)::status_actor, sqlc.narg(note))
RETURNING *;

-- name: GetReportHistory :many
SELECT * FROM report_status_history WHERE report_id = sqlc.arg(report_id)
ORDER BY id;

-- name: InsertClaimHistory :one
INSERT INTO claim_status_history (claim_id, from_status, to_status, actor, note)
VALUES (sqlc.arg(claim_id), sqlc.narg(from_status)::claim_status,
        sqlc.arg(to_status)::claim_status, sqlc.arg(actor)::status_actor, sqlc.narg(note))
RETURNING *;

-- name: GetClaimHistory :many
SELECT * FROM claim_status_history WHERE claim_id = sqlc.arg(claim_id)
ORDER BY id;
