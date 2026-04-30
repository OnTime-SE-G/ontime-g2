CREATE DATABASE route_db;
CREATE DATABASE fleet_db;
CREATE DATABASE ontime_test_db;

\connect route_db;
CREATE EXTENSION postgis;

\connect ontime_test_db;
CREATE EXTENSION postgis;