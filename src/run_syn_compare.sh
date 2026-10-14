#!/bin/bash
# run_syn_compare.sh: syn_compare.py on every FD set of E1 with designs and on the documented sets, one process per set,
# with the Java check, and with the integrity risk on the sets of E4; results/syn_compare_<set>.json and .log
cd "$(dirname "$0")/.." || exit 1
[ -f env.sh ] && . ./env.sh
P=${PYTHON:-python3}
RISK="abalone adult breast(null) bridges(null) echo(null) hepatitis(null) letter(non-dup) ncvoter(null) china_weather(null) doc-food+c1 doc-uk doc-hospital doc-tpcds"
OTHER="tpch-region tpch-nation tpch-partsupp tpch-supplier tpch-customer tpch-orders tpch-part pdbx(null) tpch-lineitem lineitem uniprot(null)"
for s in $RISK; do
    $P src/syn_compare.py --java --risk "$s" > "results/syn_compare_$(echo "$s" | tr -c 'A-Za-z0-9_\n-' _).log" 2>&1 &
done
for s in $OTHER; do
    $P src/syn_compare.py --java "$s" > "results/syn_compare_$(echo "$s" | tr -c 'A-Za-z0-9_\n-' _).log" 2>&1 &
done
wait
$P src/syn_compare.py --table > results/syn_compare.txt
date > results/syn_compare.done
