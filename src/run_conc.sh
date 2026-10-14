#!/bin/bash
# run_conc.sh: the concurrency measurement of conc.py on the five small data sets, under a uniform and a skewed
# (Zipf 1.0) choice of the copied stored records. At most 32 clients: the PostgreSQL build of the experiments
# allows 50 connections (47 for non-superusers), so 64 clients were refused (first run, 2026-10-14, kept in
# results/conc_run1/). The skewed choice runs first.
cd "$(dirname "$0")/.." || exit 1
[ -f env.sh ] && . ./env.sh
P=${PYTHON:-python3}
LOG=results/conc.log
echo "$(date +%T) start" >> $LOG
for z in 1.0 0; do
  for s in abalone breast bridges echo ncvoter; do
    $P src/conc.py --clients 1,4,16,32 --txn 10 --records 40000 --reps 3 --zipf $z $s >> $LOG 2>&1
  done
done
date > results/conc.done
