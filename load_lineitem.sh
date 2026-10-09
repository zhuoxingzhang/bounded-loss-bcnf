#!/bin/bash
# Load the HPI lineitem dump (INSERT statements with columns `0`..`15` and values wrapped in \" quotes) into
# bl.lineitem with typed columns c0..c15 in the order of the FD file (TPC-H lineitem column order).
set -e
M=/data/zzha969/mysql/server/bin/mysql
C=/data/zzha969/mysql/my.cnf
D=/data/zzha969/data/dumps
$M --defaults-file=$C --database=bl <<'SQL'
DROP TABLE IF EXISTS lineitem;
CREATE TABLE lineitem (
  `0` BIGINT NOT NULL, `1` BIGINT NOT NULL, `2` INT NOT NULL, `3` INT NOT NULL,
  `4` DECIMAL(15,2) NOT NULL, `5` DECIMAL(15,2) NOT NULL, `6` DECIMAL(15,2) NOT NULL, `7` DECIMAL(15,2) NOT NULL,
  `8` CHAR(1) NOT NULL, `9` CHAR(1) NOT NULL, `10` DATE NOT NULL, `11` DATE NOT NULL, `12` DATE NOT NULL,
  `13` CHAR(25) NOT NULL, `14` CHAR(10) NOT NULL, `15` VARCHAR(44) NOT NULL
) ENGINE=InnoDB;
SET autocommit=0;
SQL
# strip the literal \" around every value, then load inside one transaction per 1,000,000 statements
sed 's/\\"//g' $D/lineitem.sql | $M --defaults-file=$C --database=bl --init-command="SET autocommit=0; SET unique_checks=0; SET foreign_key_checks=0;"
$M --defaults-file=$C --database=bl <<'SQL'
ALTER TABLE lineitem
  RENAME COLUMN `0` TO c0, RENAME COLUMN `1` TO c1, RENAME COLUMN `2` TO c2, RENAME COLUMN `3` TO c3,
  RENAME COLUMN `4` TO c4, RENAME COLUMN `5` TO c5, RENAME COLUMN `6` TO c6, RENAME COLUMN `7` TO c7,
  RENAME COLUMN `8` TO c8, RENAME COLUMN `9` TO c9, RENAME COLUMN `10` TO c10, RENAME COLUMN `11` TO c11,
  RENAME COLUMN `12` TO c12, RENAME COLUMN `13` TO c13, RENAME COLUMN `14` TO c14, RENAME COLUMN `15` TO c15;
SELECT COUNT(*) AS lineitem_rows FROM lineitem;
SQL
echo LOAD_DONE
