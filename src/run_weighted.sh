#!/bin/bash
# run_weighted.sh: Repair and Drop under weights from random updates (weighted.py) on the FD sets with data and
# positive loss, after the re-run of the constant-attribute sets has finished (results/rerun_constants.done), so that
# no two measurements overlap; then the lookup-table runs of run_fk.sh. The weighted runs are independent and run in
# parallel, one process per set. Run from any directory on the experiment server; an optional env.sh in the
# repository root exports PGHOST, PGPORT and PGDATABASE of pgdb.py.
cd "$(dirname "$0")/.." || exit 1
[ -f env.sh ] && . ./env.sh
P=${PYTHON:-python3}
while [ ! -f results/rerun_constants.done ]; do sleep 300; done
echo "$(date +%T) re-run finished, weighted runs start"
for s in abalone breast bridges echo ncvoter weather hepatitis; do
  $P src/weighted.py --budgets 1000000 "$s" > "results/weighted_$s.log" 2>&1 &
done
wait
date > results/weighted.done
echo "$(date +%T) weighted runs done"
exec bash src/run_fk.sh
