-- name: InsertReport :one
INSERT INTO reports (
    type, category, title, description, event_date, location_text,
    contact_name, contact_email, contact_phone, tracking_token_hash, photo_path
) VALUES (
    sqlc.arg(type)::report_type, sqlc.arg(category)::report_category,
    sqlc.arg(title), sqlc.arg(description), sqlc.arg(event_date), sqlc.arg(location_text),
    sqlc.narg(contact_name), sqlc.narg(contact_email), sqlc.narg(contact_phone),
    sqlc.arg(tracking_token_hash), sqlc.narg(photo_path)
) RETURNING *;

-- name: GetReportById :one
SELECT * FROM reports WHERE id = sqlc.arg(id);
