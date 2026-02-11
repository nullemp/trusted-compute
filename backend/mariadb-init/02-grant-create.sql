-- Grant CREATE so the app can create per-job databases (tc_job_*).
-- Runs once when the MariaDB data dir is first created.
GRANT CREATE ON *.* TO 'trusted_compute'@'%';
FLUSH PRIVILEGES;
