#!/bin/bash
# run_tpcds.sh: E3 and E4 on the documented FD set of TPC-DS (documented.py: store_sales of scale factor 1 joined with
# item, store and date_dim): load and check the records, E4 and the weighted designs (as run_weighted.sh), then E3 at
# 10,000 records with five repetitions from file copies of prewarmed templates (as for weather, since the 77 exclusion
# constraints of the original relation take long to build), and the drift of drift.py last, so that no measurement
# overlaps another run. Run from any directory on the experiment server; an optional env.sh in the repository root
# exports PGHOST, PGPORT and PGDATABASE of pgdb.py.
cd "$(dirname "$0")/.." || exit 1
[ -f env.sh ] && . ./env.sh
P=${PYTHON:-python3}
LOG=results/tpcds.log
echo "$(date +%T) start" >> $LOG
$P src/documented.py --load tpcds >> $LOG 2>&1
$P src/documented.py --designs tpcds >> $LOG 2>&1
$P src/e3pg.py --check tpcds >> $LOG 2>&1
$P src/e4.py tpcds >> $LOG 2>&1
$P src/weighted.py --budgets 1000000 tpcds >> $LOG 2>&1
$P src/e3pg.py --prepare tpcds >> $LOG 2>&1
$P src/e3pg.py --copy --sizes 10000 --reps 5 tpcds >> $LOG 2>&1
echo "$(date +%T) E3 and E4 done" >> $LOG
$P src/drift.py tpcds > results/drift_tpcds.log 2>&1
date > results/tpcds.done
echo "$(date +%T) done" >> $LOG
