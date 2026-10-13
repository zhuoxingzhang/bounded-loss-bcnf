#!/bin/bash
# run_fk_rest.sh: the lookup-table mode 3nfc-f of hepatitis, which run_fk.sh did not reach because the server closed
# the connection of the 3nf-f run while it rebuilt its tables (2026-10-13 17:10). It waits for results/run_fk.done,
# so that no two measurements overlap, and measures 10,000 records only, the size the paper reports; at 20,000
# records the server terminated every backend of the original relation of hepatitis. The records are appended to
# results/e3pg_fk_hepatitis.jsonl; the paper does not report this measurement.
cd "$(dirname "$0")/.." || exit 1
[ -f env.sh ] && . ./env.sh
P=${PYTHON:-python3}
while [ ! -f results/run_fk.done ]; do sleep 300; done
echo "$(date +%T) lookup-table runs finished, hepatitis 3nfc-f starts"
nice -n 5 $P src/e3pg.py --sizes 10000 --modes 3nfc-f --out results/e3pg_fk_hepatitis.jsonl hepatitis >> results/e3pg_fk_hepatitis.log 2>&1
echo "$(date +%T) hepatitis 3nfc-f done"
date > results/run_fk_rest.done
