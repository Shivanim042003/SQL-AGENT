-- Least-privilege role for the retrieval (vector search) step.
-- It may read document_embeddings and nothing else.
-- Run as the admin user with -v ON_ERROR_STOP=1 and a retr_password variable.

CREATE ROLE app_retrieval LOGIN PASSWORD :'retr_password';

GRANT CONNECT ON DATABASE sql_agent TO app_retrieval;
GRANT USAGE ON SCHEMA public TO app_retrieval;
GRANT SELECT ON document_embeddings TO app_retrieval;

ALTER ROLE app_retrieval SET statement_timeout = '15s';
ALTER ROLE app_retrieval SET default_transaction_read_only = on;