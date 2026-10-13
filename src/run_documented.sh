#!/bin/bash
# run_documented.sh: E3 and E4 on the documented FD sets with data (documented.py: food, pricepaid, hospital), after
# the concurrency run has finished (results/conc.done), so that no two measurements overlap: load and check the
# cleaned records, E4 and the weighted designs (as run_weighted.sh), then E3 at 10,000 records with five repetitions.
# Run from any directory on the experiment server; an optional env.sh in the repository root exports PGHOST, PGPORT
# and PGDATABASE of pgdb.py.
cd "$(dirname "$0")/.." || exit 1
[ -f env.sh ] && . ./env.sh
P=${PYTHON:-python3}
LOG=results/documented.log
while [ ! -f results/conc.done ]; do sleep 60; done
echo "$(date +%T) start" >> $LOG
$P src/documented.py --load >> $LOG 2>&1
$P src/documented.py --designs >> $LOG 2>&1
$P src/e3pg.py --check food pricepaid hospital >> $LOG 2>&1
$P src/e4.py food pricepaid hospital >> $LOG 2>&1
for s in food pricepaid hospital; do
  $P src/weighted.py --budgets 1000000 "$s" >> $LOG 2>&1
done
for s in hospital food pricepaid; do
  $P src/e3pg.py --sizes 10000 --reps 5 "$s" >> $LOG 2>&1
done
date > results/documented.done
echo "$(date +%T) done" >> $LOG
