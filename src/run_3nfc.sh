#!/bin/bash
# run_3nfc.sh: E3 and E4 again for the classical 3NF synthesis after it became DecompAlg4 of the iCONF experiments
# (experiments.py --patch-3nfc, meaningful.py --patch-3nfc and documented.py --designs updated the E1 records).
# E4 is rerun on every set (the other designs keep their risks, since the updates depend only on the seed). In E3, the
# modes 3nfc-x and 3nfc are measured again at 10,000 records; where DecompAlg4 returns the design of iCONF, e3pg.py
# --known records that it shares the measurement of 3nf-x (3nf). The sets whose design changed are measured one after
# the other and after the E3 measurements of run_tpcds.sh, while its drift.py and the E4 run of TPC-DS (computations
# in Python only) proceed. FROM=2 starts at that point.
cd "$(dirname "$0")/.." || exit 1
[ -f env.sh ] && . ./env.sh
P=${PYTHON:-python3}
LOG=results/run_3nfc.log
echo "$(date +%T) start" >> $LOG
if [ "${FROM:-1}" -le 1 ]; then
    for s in abalone adult breast bridges echo hepatitis letter ncvoter weather food pricepaid hospital; do
        $P src/e4.py $s > results/e4_$s.log 2>&1
        echo "$(date +%T) e4 $s exit $?" >> $LOG
    done
    $P src/embedded_loss.py --tex >> $LOG 2>&1
    # the sets on which DecompAlg4 returns the design of iCONF: references only, no measurement
    for s in adult breast letter; do
        $P src/e3pg.py --sizes 10000 --reps 5 --modes 3nfc-x,3nfc --known orig-x,keys,3nf-x,3nf $s >> $LOG 2>&1
    done
    for s in food pricepaid hospital; do
        $P src/e3pg.py --sizes 10000 --reps 5 --modes 3nfc-x --known orig-x,keys,3nf-x $s >> $LOG 2>&1
    done
fi
echo "$(date +%T) waiting for the E3 measurements of TPC-DS" >> $LOG
until grep -q "E3 and E4 done" results/tpcds.log; do sleep 60; done
( $P src/e4.py tpcds > results/e4_tpcds.log 2>&1; echo "$(date +%T) e4 tpcds exit $?" >> $LOG ) &
for s in abalone bridges echo ncvoter hepatitis; do
    $P src/e3pg.py --sizes 10000 --reps 5 --modes 3nfc-x,3nfc --known orig-x,keys,3nf-x,3nf $s >> $LOG 2>&1
    echo "$(date +%T) e3 $s exit $?" >> $LOG
done
$P src/e3pg.py --copy --sizes 10000 --reps 5 --modes 3nfc-x,3nfc --known orig-x,keys,3nf-x,3nf weather >> $LOG 2>&1
echo "$(date +%T) e3 weather exit $?" >> $LOG
wait
date > results/run_3nfc.done
echo "$(date +%T) done" >> $LOG
