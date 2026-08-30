-- Runs once, on first initialisation of the data volume.
-- The application database (kanbai) is created by POSTGRES_DB; this adds the one
-- the test suite runs against, so tests never touch development data.
CREATE DATABASE kanbai_test OWNER kanbai;
