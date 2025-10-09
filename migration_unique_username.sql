-- migration_unique_username.sql
-- Run this against your MariaDB database to add unique constraint

USE `tatou`;

-- Check for duplicate usernames first
SELECT login, COUNT(*) as count 
FROM Users 
GROUP BY login 
HAVING count > 1;

-- If no duplicates shown above, run this:
ALTER TABLE `Users` 
ADD CONSTRAINT `uq_users_login` UNIQUE (`login`);

-- Verify the constraint was added
SHOW CREATE TABLE `Users`;