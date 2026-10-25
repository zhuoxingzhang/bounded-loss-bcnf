#!/bin/bash
# run_v2.sh: every experiment of the paper on one machine, under Linux (PostgreSQL 18.4 built from source in ~/kloss)
# or Windows (Git Bash; the official PostgreSQL 18.4 in C:\kloss), port 55435, in the order of their dependencies:
#   0  a copy of the earlier records, the source tables that are still missing, the buffer size and the WAL limit
#      (16 GB and 64 GB under Linux, 32 GB and 8 GB for the small Windows disk), the check of the FDs and keys on the
#      source tables
#   1  E1 on the discovered and the meaningful FD sets, the greedy BCNF decomposition and Hybrid (six at a time)
#   2  integrity risk, violation weights, the bounds, the examples, the validation runs and the cross-checks, then
#      drift, the stored risks, independence and parts, Hit and the risks of the teaser (four at a time)
#   3  the PostgreSQL timings, one at a time and alone on the machine: insertions (E3; the modes whose exclusion
#      constraints take hours to build from templates, one set at a time and after checks of the free space), with
#      foreign keys, the queries, the teaser and the concurrency check
#   4  the tables and figures, a list of the records that this run did not write, and the checks of the theory (E8)
# Under Windows the driver and its children, PostgreSQL included, run on the performance cores (logical processors 0
# to 15).
# Every step leaves a marker in results/run_v2/done/, so that a restart skips the steps already done; the log is
# results/run_v2/run.log and the output of step S is results/run_v2/S.log.
# usage: bash src/run_v2.sh          (from any directory; DRY=1 L=<dir> lists the steps without running them)
set -u
cd "$(dirname "$0")/.."
export PGHOST=localhost PGPORT=55435 PGDATABASE=bcnf PYTHONIOENCODING=utf8
if [ -e /proc/$$/winpid ]; then
    K=/c/kloss X=.exe PY=/c/kloss/venv/Scripts/python.exe SB=32GB WAL=8GB
    pwsh -NoProfile -Command "(Get-Process -Id $(cat /proc/$$/winpid)).ProcessorAffinity = 0xFFFF"
    free_bytes() { pwsh -NoProfile -Command "(Get-PSDrive C).Free"; }
else
    K=$HOME/kloss X= PY=$HOME/kloss/venv/bin/python SB=16GB WAL=64GB
    PGHOST=$K/sock   # a private socket directory: the server has no TCP port on a shared machine
    echo 500 > /proc/self/oom_score_adj   # on a shared machine, a lack of memory ends these processes first
    free_bytes() { df -B1 --output=avail $K | tail -n 1; }
fi
export K X PY SB WAL PG=$K/pgsql/bin L=${L:-results/run_v2} DRY=${DRY:-}
mkdir -p $L/done
[ -e $L/start ] || date '+%F %T' > $L/start

log() { echo "$(date '+%F %T') $*" | tee -a $L/run.log; }
disk() { log "$K has $(( $(free_bytes) >> 30 )) GB free"; }
step() {   # step NAME command...: runs the command once
    local name=$1; shift
    [ -e "$L/done/$name" ] && return 0
    [ -n "$DRY" ] && { log "dry $name: $*"; return 0; }
    log "start $name (load $(cut -d' ' -f1-3 /proc/loadavg))"
    if "$@" >> "$L/$name.log" 2>&1 < /dev/null; then touch "$L/done/$name"; log "done $name"; else log "FAILED $name (exit $?)"; fi
}
lanes() {   # lanes K: the steps of stdin ("name command ..." per line), K at a time
    xargs -P "$1" -L 1 bash -c 'step "$@"' _
}
fresh() {   # fresh FILE command...: the command on a removed FILE (for the drivers that append)
    local f=$1; shift
    rm -f "$f" && "$@"
}
e1one() {   # E1 on one FD set within the four hours of experiments.py
    timeout 14400 $PY src/experiments.py --one "$1"
    local rc=$?
    [ $rc = 124 ] || return $rc
    echo "{\"name\": \"$1\", \"error\": \"timeout after 14400 s\"}" > "results/e1_$($PY -c "import sys; sys.path.insert(0, 'src'); import experiments; print(experiments.safe(sys.argv[1]))" "$1").jsonl"
}
restore() {   # restore TABLE: the source table from the dump, unless the database has it
    [ -n "$($PG/psql$X -Atc "SELECT to_regclass('src.$1')")" ] && return 0
    $PG/pg_restore$X -d bcnf --no-owner -n src -t $1 $K/src_dump.pgc &&
    $PG/psql$X -v ON_ERROR_STOP=1 -c "ANALYZE src.$1"
}
buffers() {
    $PG/psql$X -v ON_ERROR_STOP=1 -c "ALTER SYSTEM SET shared_buffers = '$SB'" &&
    $PG/psql$X -v ON_ERROR_STOP=1 -c "ALTER SYSTEM SET max_wal_size = '$WAL'" &&
    $PG/pg_ctl$X -D $K/pgdata -l $K/pg.log -w -m fast restart &&
    $PG/psql$X -Atc "SHOW shared_buffers" -c "SHOW max_wal_size"
}
into() {   # into FILE command...: the output of the command in FILE
    local f=$1; shift
    "$@" > "$f"
}
closures() {   # the digests of the C and the Python closures (closure_check.py) must agree
    $PY src/closure_check.py results/closure_c.json && FDLIB_PYTHON=1 $PY src/closure_check.py results/closure_py.json &&
    $PY -c "import json; a, b = (json.load(open('results/closure_%s.json' % x)) for x in ('c', 'py')); strip = lambda d: {k: {f: v for f, v in r.items() if f != 'seconds'} for k, r in d.items() if k != 'c'}; assert a['c'] and not b['c'] and strip(a) == strip(b), 'the digests differ'; print('C and Python closures agree on', len(strip(a)), 'FD sets')"
}
room() {   # room SET: the disk holds a file copy of the largest template of SET with 10 GB to spare
    local need free
    need=$($PG/psql$X -Atc "SELECT coalesce(max(pg_database_size(datname)), 0) FROM pg_database WHERE datname LIKE 'e3t\_$1\_%' AND datname NOT IN ('e3t_$1_base', 'e3t_$1_run')")
    free=$(free_bytes)
    log "room for $1: largest template $((need >> 30)) GB, free $((free >> 30)) GB"
    [ $((free - need)) -gt $((10 << 30)) ]
}
heavy_of() {   # the modes of HEAVY for a set, comma-separated
    for h in $HEAVY; do [ "${h%%:*}" = "$1" ] && printf '%s,' "${h#*:}"; done | sed 's/,$//'
}
light_of() {   # the other modes of E3MODES
    local hv=",$(heavy_of $1),"
    for m in ${E3MODES//,/ }; do case "$hv" in *",$m,"*) ;; *) printf '%s,' $m;; esac; done | sed 's/,$//'
}
prepare() {   # prepare SET MODE: the template of the mode, if the disk has the room of ROOM for the set
    local need=0 free h
    for h in $ROOM; do [ "${h%%:*}" = "$1" ] && need=${h#*:}; done
    free=$(( $(free_bytes) >> 30 ))
    log "prepare $1 $2: $free GB free, $need GB needed"
    [ $free -ge $need ] && $PY src/e3pg.py --prepare --modes $2 $1
}
heavy() {   # heavy SET MODES: the modes on copies of their templates, if the disk has room for a copy
    room $1 && $PY src/e3pg.py --sizes 10000 --reps 5 --modes $2 --copy $1
}
heavyset() {   # the templates of the heavy modes of a set, their timed copies, and the removal of the templates
    local s=$1 hv
    hv=$(heavy_of $1)
    for m in ${hv//,/ }; do echo "prepare_${s}_$m prepare $s $m"; done | lanes 4
    step e3_$s heavy $s $hv
    step dropdbs_$s dropdbs $s
}
dropdbs() {   # the template databases of e3pg.py --copy for one set
    for d in $($PG/psql$X -Atc "SELECT datname FROM pg_database WHERE datname LIKE 'e3t\_$1\_%'"); do
        $PG/psql$X -v ON_ERROR_STOP=1 -c "DROP DATABASE \"$d\"" || return 1
    done
}
export -f log step fresh e1one into closures prepare free_bytes

DISCOVERED="hepatitis(null) uniprot(null) diabetic(null) fd-red lineitem tpch-lineitem china_weather(null) ncvoter(null)
            pdbx(null) echo(null) bridges(null) letter(non-dup) adult breast(null) abalone tpch-part tpch-orders
            tpch-customer tpch-supplier tpch-partsupp tpch-nation tpch-region"
MEANINGFUL="tpcds food food+c1 hospital hospital-all tpcds-core uk uk+admin"
DATA="tpcds weather hepatitis pricepaid food ncvoter echo bridges letter adult abalone breast hospital tpch_part tpch_orders"
WEIGHTED="hepatitis weather tpcds ncvoter pricepaid food echo bridges abalone breast hospital"
HIT_UNIT="uniprot(null) tpch-lineitem hepatitis(null) china_weather(null) ncvoter(null) doc-tpcds doc-uk doc-food+c1
          doc-hospital adult letter(non-dup) echo(null) bridges(null) breast(null) abalone"
HIT_W="hepatitis(null) china_weather(null) ncvoter(null) doc-tpcds doc-uk doc-food+c1 doc-hospital echo(null)
       bridges(null) breast(null) abalone"
E3SETS="breast bridges echo abalone adult letter ncvoter hepatitis hospital food pricepaid weather tpcds"
# the modes whose exclusion constraints take hours to build run on file copies of templates (e3pg.py --copy)
HEAVY="weather:orig-x weather:3nf-x weather:3nfc-x tpcds:orig-x"
# the free space (GB) that the templates of a set and one file copy need, estimated from the GiST indexes
export ROOM="weather:30 tpcds:60"
E3MODES=orig-x,3nf-x,3nfc-x,3nf,3nfc,keys,bcnf,gbcnf,repair,drop
FKMODES=keys,3nf,bcnf,gbcnf,repair,drop

disk
log "phase 0: records, source tables, buffers"
step backup tar cf $K/results_v1_server.tar results
for t in $DATA; do step restore_$t restore $t; done
step buffers buffers
step check $PY src/e3pg.py --check $DATA

disk
log "phase 1: E1, greedy BCNF, Hybrid"
{
    for s in $DISCOVERED; do echo "e1_$s e1one $s"; done
    for s in $MEANINGFUL; do echo "meaningful_$s $PY src/meaningful.py --one $s"; done
    for s in $DISCOVERED; do
        case $s in diabetic\(null\)|fd-red) ;; *) echo "gbcnf_$s $PY src/gbcnf.py $s";; esac
        echo "hybrid_$s $PY src/hybrid.py $s"
    done
} | lanes 6
step documented $PY src/documented.py --designs food pricepaid hospital tpcds

disk
log "phase 2: risks, weights, bounds, checks, Hit"
{
    for s in $WEIGHTED; do echo "weighted_$s $PY src/weighted.py --budgets 1000000 $s"; done
    echo "validate_n5 into logs/validate_n5f.log $PY src/validate_fdlib.py 5 86400 32 300322"
    echo "validate_n6 into logs/validate_n6e.log $PY src/validate_fdlib.py 6 86400 31 73730"
    for s in $DATA; do echo "e4_$s $PY src/e4.py $s"; done
    echo "obstructions fresh results/obstructions.jsonl $PY src/obstruction_stats.py"
    echo "examples $PY src/test_examples.py"
    echo "closure_check closures"
    echo "iconf_check into results/iconf_check.log $PY src/iconf_check.py"
    echo "decomp4_check into results/decomp4_check.log $PY src/decomp4_check.py"
    echo "teaser_risk fresh results/teaser_risk.jsonl $PY src/teaser_risk.py"
} | lanes 4
{
    for s in $HIT_UNIT; do echo "hit_unit_$s $PY src/hit.py --core --time 3600 $s"; done
    for s in $HIT_W; do echo "hit_w_$s $PY src/hit.py --core --time 3600 --weights $s"; done
    for s in $WEIGHTED; do echo "drift_$s $PY src/drift.py $s"; done
    for s in $DATA; do echo "stored_$s $PY src/stored_risk.py $s"; done
    echo "independence $PY src/independence.py"
} | lanes 4

disk
log "phase 3: PostgreSQL timings"
for s in $E3SETS; do
    hv=$(heavy_of $s)
    if [ -n "$hv" ]; then
        step clear_e3_$s rm -f results/e3pg_$s.jsonl
        step e3b_$s $PY src/e3pg.py --sizes 10000 --reps 5 --modes $(light_of $s) $s
        [ $s = tpcds ] || heavyset $s
    else
        step e3_$s fresh results/e3pg_$s.jsonl $PY src/e3pg.py --sizes 10000 --reps 5 --modes $E3MODES $s
    fi
done
for s in $E3SETS; do
    step fk_$s fresh results/e3pg_fks_$s.jsonl $PY src/e3pg.py --sizes 10000 --reps 5 --modes $FKMODES --fks $s
done
for s in $E3SETS; do step queries_$s fresh results/queries_$s.jsonl $PY src/queries.py --reps 5 --lookups 1000 $s; done
step teaser fresh results/teaser_pg.jsonl $PY src/teaser_pg.py --designs D1,D2,D4,3NF+exclude,D1+exclude
step concurrency into results/concurrency_check.log $PY src/concurrency_check.py
heavyset tpcds   # last, since its template and copy need the most disk

disk
log "phase 4: tables, figures, stale records, checks of the theory"
step tables $PY src/paper_tables.py
step figures $PY src/paper_figures.py
step ablation $PY src/ablation.py --tex
step embedded $PY src/embedded_loss.py --tex
find results -maxdepth 1 -type f ! -newer $L/start | sort > $L/not_rewritten.txt
log "$(wc -l < $L/not_rewritten.txt) files in results/ predate this run (results/run_v2/not_rewritten.txt)"
python3() { $PY "$@"; }
export -f python3
step e8 bash -c 'bash e8/run_validation.sh && mkdir -p results/e8 && cp e8/validation_logs/* results/e8/'

touch $L/run_v2.done
log "all done"
