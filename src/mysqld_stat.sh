#!/bin/bash
# Sample the resident memory, CPU time and CPU share of the user-space MySQL server every 30 s
# (the server's watchdog has shut mysqld down three times; the samples show what it saw).
out=${1:-results/mysqld_stat.log}   # run from the repository root, or give the log file as the argument
while p=$(pgrep -f "^./server/bin/mysqld" | head -n 1); [ -n "$p" ]; do
  rss=$(awk '/VmRSS/{printf "%.1f", $2/1048576}' /proc/$p/status)
  cpu=$(ps -o time= -p $p | tr -d ' ')
  pct=$(top -b -n 1 -p $p | tail -n 1 | awk '{print $9}')
  echo "$(date +%T) rss_gb $rss cpu $cpu pct $pct" >> $out
  sleep 30
done
