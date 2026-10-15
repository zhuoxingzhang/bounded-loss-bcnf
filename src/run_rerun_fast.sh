#!/bin/bash
# run_rerun_fast.sh: re-runs every experiment that depends on the designs of Repair and Drop with the C closures of
# fdlib, the iterated ascent and the design construction with fewer schemata (2026-10-15; the records of the previous
# version are kept in results/*_before_fast/):
#  1. E1 on every FD set (e1_relaunch.sh, one process per set) and the validation runs, in the background;
#  2. the documented sets (meaningful.py) and their E1 records (documented.py --designs);
#  3. per set, once its E1 record is fresh: the weighted runs and then the drift runs (in the background);
#  4. per set, in the order in which the E1 records arrive: E3 for the modes among repair and drop whose design
#     differs from the previous version (design_diff.canon against results/e1_before_fast), then E4; one measurement
#     after another.
# Run from any directory on the experiment server; an optional env.sh in the repository root exports PGHOST, PGPORT
# and PGDATABASE of pgdb.py.
cd "$(dirname "$0")/.." || exit 1
[ -f env.sh ] && . ./env.sh
P=${PYTHON:-python3}
LOG=results/rerun_fast.log
MARK=results/rerun_fast.start
log() { echo "$(date '+%F %T') $*" >> $LOG; }

e1file() { $P -c "import sys; sys.path.insert(0, 'src'); import e3, experiments; print('results/e1_%s.jsonl' % experiments.safe(e3.SETS[sys.argv[1]]))" "$1"; }
wait_fresh() { f=$(e1file "$1"); while [ ! "$f" -nt $MARK ]; do sleep 300; done; }

changed_modes() {  # the modes among repair and drop whose design differs from the previous version
  $P - "$1" <<'EOF'
import sys, os, json
sys.path.insert(0, "src")
import e3, experiments
from design_diff import canon
f = "e1_%s.jsonl" % experiments.safe(e3.SETS[sys.argv[1]])
def last(p):
    L = [l for l in open(p, encoding="utf-8") if l.strip()] if os.path.isfile(p) else []
    return json.loads(L[-1]) if L else {}
n, o = last(os.path.join("results", f)), last(os.path.join("results", "e1_before_fast", f))
print(",".join(m for m in ("repair", "drop")
               if m in n.get("designs", {}) and canon(n["designs"][m]) != canon(o.get("designs", {}).get(m))))
EOF
}

drop_templates() {  # drop_templates <set> <modes>: the template databases of e3pg.py --copy
  $P - "$@" <<'EOF'
import sys
sys.path.insert(0, "src")
from pgdb import connect, qi
con = connect(autocommit=True)
for m in sys.argv[2].split(","):
    con.cursor().execute("DROP DATABASE IF EXISTS %s WITH (FORCE)" % qi("e3t_%s_%s" % (sys.argv[1], m)))
EOF
}

compute() {  # the weighted and the drift runs of one set, once its E1 record is fresh
  wait_fresh "$1"
  $P src/weighted.py --budgets 1000000 "$1" > "results/weighted_$1.log" 2>&1
  $P src/drift.py "$1" > "results/drift_$1.log" 2>&1
  log "$1: weighted and drift done"
}

e34() {  # E3 of the changed modes, then E4
  modes=$(changed_modes "$1")
  if [ -z "$modes" ]; then log "$1: no design changed"; return; fi
  log "$1: E3 of $modes"
  case "$1" in
    weather)
      $P src/e3pg.py --prepare --modes "$modes" weather >> results/e3pg_weather.log 2>&1
      $P src/e3pg.py --copy --modes "$modes" weather >> results/e3pg_weather.log 2>&1
      drop_templates weather "$modes" ;;
    tpcds)
      $P src/e3pg.py --prepare --modes "$modes" tpcds >> results/tpcds.log 2>&1
      $P src/e3pg.py --copy --sizes 10000 --reps 5 --modes "$modes" tpcds >> results/tpcds.log 2>&1
      drop_templates tpcds "$modes" ;;
    food|pricepaid|hospital)
      $P src/e3pg.py --sizes 10000 --reps 5 --modes "$modes" "$1" >> results/documented.log 2>&1 ;;
    *)
      $P src/e3pg.py --modes "$modes" "$1" >> "results/e3pg_$1.log" 2>&1 ;;
  esac
  $P src/e4.py "$1" >> results/e4_rerun_fast.log 2>&1
  log "$1: E3 and E4 done"
}

log "start"
touch $MARK
for d in e1 meaningful weighted drift e4 e3pg; do
  mkdir -p results/${d}_before_fast
  cp -n results/${d}_*.jsonl results/${d}_before_fast/ 2>/dev/null
done
mapfile -t SETS1 < <($P -c "import sys; sys.path.insert(0, 'src'); import experiments as e
print('\n'.join(s[0] for s in e.SETS if s[0] not in ('diabetic(null)', 'fd-red')))")
bash src/e1_relaunch.sh fast "${SETS1[@]}" >> $LOG 2>&1
log "E1 launched on ${#SETS1[@]} sets"
nice -n 19 $P src/validate_fdlib.py 5 14400 32 300322 > logs/validate_n5f.log 2>&1 &
nice -n 19 $P src/validate_fdlib.py 6 14400 31 73730 > logs/validate_n6e.log 2>&1 &
nice -n 19 $P src/meaningful.py --parallel 8 > results/meaningful_rerunfast.log 2>&1
$P src/documented.py --designs >> $LOG 2>&1
log "documented sets done"
for s in abalone breast bridges echo ncvoter weather hepatitis food pricepaid hospital tpcds; do
  compute $s &
done
sleep 300   # the weighted runs of the sets ready now load their source tables before the first measurement
for s in abalone breast bridges echo adult letter food pricepaid hospital tpcds ncvoter hepatitis weather; do
  wait_fresh $s
  e34 $s
done
log "E3 and E4 done, waiting for the weighted, drift and validation runs"
wait
date > results/rerun_fast.done
log "done"
