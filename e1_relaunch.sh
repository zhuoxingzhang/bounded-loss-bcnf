#!/bin/bash
# e1_relaunch.sh: stop the running E1 processes and re-run the FD sets with positive loss, one process each.
# usage: bash e1_relaunch.sh <tag>      (logs go to results/e1_rerun<tag>_<safe name>.log)
cd /data/zzha969/bounded-loss-bcnf || exit 1
tag="$1"
for pid in $(pgrep -f "^python3 experiments.py --one"); do
    kill "$pid" && echo "killed $pid"
done
sleep 2
for s in "abalone" "breast(null)" "bridges(null)" "echo(null)" "ncvoter(null)" "china_weather(null)" "tpch-lineitem" "lineitem" "uniprot(null)" "hepatitis(null)"; do
    safe=$(python3 -c "import experiments,sys; print(experiments.safe(sys.argv[1]))" "$s")
    setsid nohup nice -n 19 python3 experiments.py --one "$s" > "results/e1_rerun${tag}_${safe}.log" 2>&1 < /dev/null &
done
sleep 4
ps -eo pid,etime,args | grep "[^ ]python3 experiments.py --one" | cut -c1-70
pgrep -fc "^python3 experiments.py --one"
