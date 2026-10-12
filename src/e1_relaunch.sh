#!/bin/bash
# e1_relaunch.sh: stop the running E1 processes and re-run FD sets, one process each.
# usage: bash src/e1_relaunch.sh <tag> [set ...]   (from the repository root)   (default: the ten sets with positive loss;
#        logs go to results/e1_rerun<tag>_<safe name>.log)
cd "$(dirname "$0")/.." || exit 1
tag="$1"; shift
if [ $# -eq 0 ]; then
    set -- "abalone" "breast(null)" "bridges(null)" "echo(null)" "ncvoter(null)" "china_weather(null)" "tpch-lineitem" "lineitem" "uniprot(null)" "hepatitis(null)"
fi
for pid in $(pgrep -f "^python3 src/experiments.py --one"); do
    kill "$pid" && echo "killed $pid"
done
sleep 2
for s in "$@"; do
    safe=$(python3 -c "import sys; sys.path.insert(0, 'src'); import experiments; print(experiments.safe(sys.argv[1]))" "$s")
    setsid nohup nice -n 19 python3 src/experiments.py --one "$s" > "results/e1_rerun${tag}_${safe}.log" 2>&1 < /dev/null &
done
sleep 4
pgrep -fa "^python3 src/experiments.py --one" | cut -c1-70
