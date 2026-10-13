#!/bin/bash
# run_fk_weather.sh: the lookup-table modes orig-f and 3nf-f of weather at 10,000 records with five repetitions, each
# from a file copy of a prewarmed template (--copy), since building these tables takes over an hour and the server
# terminated the rebuilds of the run of run_fk.sh (2026-10-13). The templates are built first (--prepare); a template
# whose build completed is reused, so a step that loses its connection is simply started again. Each mode is measured
# on its own, so that a crash in one mode does not repeat the other. The records are appended to
# results/e3pg_fk_weather.jsonl, whose earlier run without --copy holds one repetition of orig-f; paper_tables.py
# uses the last run of a design.
cd "$(dirname "$0")/.." || exit 1
[ -f env.sh ] && . ./env.sh
P=${PYTHON:-python3}
OUT=results/e3pg_fk_weather.jsonl
LOG=results/e3pg_fk_weather.log
for mode in orig-f 3nf-f; do
  for attempt in 1 2 3; do
    nice -n 5 $P src/e3pg.py --prepare --modes $mode --out $OUT weather >> $LOG 2>&1 && break
    echo "$(date +%T) template of $mode failed (attempt $attempt)" >> $LOG
    sleep 60
  done
done
for mode in orig-f 3nf-f; do
  for attempt in 1 2 3; do
    nice -n 5 $P src/e3pg.py --sizes 10000 --modes $mode --copy --out $OUT weather >> $LOG 2>&1 && break
    echo "$(date +%T) measurement of $mode failed (attempt $attempt)" >> $LOG
    sleep 60
  done
done
date > results/run_fk_weather.done
