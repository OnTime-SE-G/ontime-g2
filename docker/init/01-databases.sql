CREATE DATABASE fleet_db;
CREATE DATABASE eta_db;
CREATE DATABASE anomaly_db;
CREATE DATABASE ontime_test_db;

\connect ontime_db;
CREATE EXTENSION postgis;

\connect ontime_test_db;
CREATE EXTENSION postgis;
