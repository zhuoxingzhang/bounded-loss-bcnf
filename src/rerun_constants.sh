#!/bin/bash
# rerun_constants.sh: re-runs every experiment on the FD sets whose constant attribute drop_constants.py removed
# (echo, ncvoter, uniprot and TPC-H orders): E1 with the greedy BCNF decomposition and Hybrid on all four, then E3
# and E4 on the two with data in PostgreSQL (echo, ncvoter). Run from any directory on the experiment server; an
# optional env.sh in the repository root exports PGHOST, PGPORT and PGDATABASE of pgdb.py.
cd "$(dirname "$0")/.." || exit 1
[ -f env.sh ] && . ./env.sh
P=${PYTHON:-python3}
for s in "echo(null)" "ncvoter(null)" "uniprot(null)" tpch-orders; do
  $P src/experiments.py --one "$s" > "results/e1_rerun_$(echo "$s" | tr -d '()').log" 2>&1 &
done
wait
$P src/gbcnf.py "echo(null)" "ncvoter(null)" "uniprot(null)" tpch-orders > results/gbcnf_rerun.log 2>&1
$P src/hybrid.py "echo(null)" "ncvoter(null)" "uniprot(null)" tpch-orders > results/hybrid_rerun.log 2>&1
for t in echo ncvoter; do
  $P src/e3pg.py --modes orig-x,3nf-x,3nfc-x,3nf,3nfc,keys,bcnf,gbcnf,repair,drop "$t" > "results/e3pg_rerun_$t.log" 2>&1
  $P src/e4.py "$t" > "results/e4_rerun_$t.log" 2>&1
done
date > results/rerun_constants.done
