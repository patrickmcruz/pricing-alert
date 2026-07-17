-- Runs once when the `db` container's data volume is first created
-- (postgres' docker-entrypoint-initdb.d convention). Creates the secondary
-- databases on the same instance so pytest and local APP_ENV=develop runs
-- each get their own isolated data and never touch the production database
-- (see config.toml - [develop] and [test] point at these, [production]
-- points at "pricing").
CREATE DATABASE pricing_test;
CREATE DATABASE pricing_dev;
