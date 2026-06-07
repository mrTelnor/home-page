-- Creates the `knowledge` database on first Postgres startup (fresh volume).
-- For existing prod volumes this won't run automatically — handled in Phase 5
-- Task 5.0 via manual ansible command.
SELECT 'CREATE DATABASE knowledge'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'knowledge')\gexec
