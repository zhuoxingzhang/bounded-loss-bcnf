#!/bin/bash
# run_fk.sh: the lookup-table baseline of E3 (modes orig-f, 3nf-f and 3nfc-f of e3pg.py: every non-key FD of the
# original relation and of the critical schemata of the two 3NF syntheses enforced by a lookup table with a foreign
# key instead of an exclusion constraint) on the FD sets with data, after the re-run of the constant-attribute sets
# has finished (results/rerun_constants.done), so that no two measurements overlap. The sets run one after another,
# the smallest first. Run from any directory on the experiment server; an optional env.sh in the repository root
# exports PGHOST, PGPORT and PGDATABASE of pgdb.py.
cd "$(dirname "$0")/.." || exit 1
[ -f env.sh ] && . ./env.sh
P=${PYTHON:-python3}
while [ ! -f results/rerun_constants.done ]; do sleep 300; done
echo "$(date +%T) re-run finished, lookup-table modes start"
for s in breast bridges echo abalone adult letter ncvoter tpch_part tpch_orders hepatitis weather; do
  nice -n 5 $P src/e3pg.py --modes orig-f,3nf-f,3nfc-f "$s" >> "results/e3pg_$s.log" 2>&1
  echo "$(date +%T) $s done"
done
date > results/run_fk.done
