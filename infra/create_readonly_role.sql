CREATE ROLE app_readonly WITH LOGIN PASSWORD :'ro_password';

GRANT CONNECT ON DATABASE sql_agent TO app_readonly;

GRANT USAGE ON SCHEMA public TO app_readonly;

GRANT SELECT ON distribution_centers, events, inventory_items, order_items, orders, products, users TO app_readonly;

REVOKE TEMPORARY ON DATABASE sql_agent FROM PUBLIC;
