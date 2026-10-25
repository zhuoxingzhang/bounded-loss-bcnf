#!/bin/bash
# E8: machine checks of the theoretical results (exhaustive or randomized; small schemata).
# Each line names the paper result it supports. Run from anywhere; outputs go to ./validation_logs.
set -u
D="$(cd "$(dirname "$0")" && pwd)"; L="$D/validation_logs"; mkdir -p "$L"
run() { echo "== $1"; shift; python3 -I "$@" 2>&1 | tee "$L/$(basename "$1" .py).log" | tail -5; }
run "Solver reproduces all examples of the paper (Thms. restrictions, Props. weakenings/local/cover-tight)" "$D/validate.py" "$D"
run "Prop. Price of plainness: antichain family, loss 1 vs plain loss C(m,m/2)"            "$D/q1.py" "$D"
run "Prop. Price of plainness: plain minimum n for the singleton family"                  "$D/plain_check.py"
run "Thm. Correctness of Hit: prototype vs exhaustive search (400 random schemata)"        "$D/hitloop_test.py" "$D"
run "Thm. Realizability: atomic cover of the reduction (60 random formulas)"              "$D/cover_check.py" "$D"
run "Thm. Realizability: Delta realizable iff formula unsatisfiable (slow beyond 9 attrs)" "$D/conp_check.py" "$D"
run "Thm. Independence: criterion vs brute-force chase (5,400 random designs)"            "$D/indep_test2.py" "$D"
run "Thm. Decomposition by sources: additivity on random source-separated schemata"       "$D/srcsep.py" "$D"
run "Thm. Decomposition by sources: three parts, more instances"                           "$D/srcsep2.py" "$D"
run "Conjecture (sources): glued weakening gadgets, where weakened FDs matter (slow)"      "$D/srcsep3.py" "$D"
run "Projections need not preserve enforceability (motivates the conjecture)"              "$D/contract2.py" "$D"
run "Open question: local weakened FDs suffice under unit weights (random search, 15 min)" "$D/q2search.py" "$D" "$L/q2_out.json" 900
run "Open question: local weakened FDs, context-replicated variants (slow)"                 "$D/q2ctx.py" "$D" 2
