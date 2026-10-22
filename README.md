# Boyce-Codd Normal Form with Bounded Dependency Loss

Code, FD sets and experiment records of the paper "Boyce-Codd Normal Form with Bounded Dependency Loss", and its
appendix `appendix.pdf` (Appendix A: further results, Appendix B: all proofs, numbered as in the paper).

## Requirements

Python 3.13. The algorithms use the standard library only. `fdlib.py` compiles the closures of `src/closure.c` with
gcc at its first import and otherwise runs them in Python (also on Windows, above 64 attributes, or with
`FDLIB_PYTHON=1`). The database experiments need PostgreSQL 18 with `btree_gist` and `pg_prewarm`, psycopg2 and
NumPy, and MySQL 8 with pymysql for staging the source tables. `pgdb.py` reads `PGHOST`, `PGPORT` and `PGDATABASE`;
`e3load.py` reads `MYSQL_SOCKET`, `HPI_CSV_DIR` and `ICONF_DB`.

## Layout

| path | content |
|---|---|
| `src/` | algorithms, experiment drivers, checks, and the scripts that write the tables and figures |
| `data/fds/` | the FD sets of the experiments |
| `results/` | the record of every run (`<experiment>_<set>.jsonl`) and the tables (`table_*.tex`) and figures (`fig_*.tex`) of the paper |
| `logs/` | the validation runs |
| `search/` | the random and exhaustive searches behind the counterexamples of the paper, with their logs |
| `iconf/` | Java drivers that run the original iCONF and DecompAlg4 for the cross-checks (`iconf/README.md`) |

Every script states its purpose and options in its docstring and runs from the repository root. The main ones:

| scripts in `src/` | purpose |
|---|---|
| `fdlib.py`, `closure.c` | closures, minimal keys, atomic cover Σ_a, enforceability test, BCNF designs, dependency loss, classical BCNF decomposition |
| `drop.py`, `ascend.py`, `repair.py` | the algorithms Drop, Ascend and Repair |
| `iconf.py`, `gbcnf.py`, `hybrid.py` | competitors: iCONF and the classical 3NF synthesis DecompAlg4, the greedy BCNF decomposition, Opt and Hybrid of Wei and Link |
| `experiments.py`, `meaningful.py` | E1 and E2 on the discovered and on the meaningful FD sets |
| `documented.py` | the data of the meaningful FD sets for E3 and E4 |
| `e3load.py`, `pgload.py`, `e3pg.py`, `e3_report.py` | E3: source tables in MySQL and PostgreSQL, insertion times, summary |
| `e4.py`, `weighted.py`, `drift.py` | E4: integrity risk, violation weights, drift |
| `teaser_pg.py` | the running example of the introduction |
| `test_examples.py`, `validate_fdlib.py`, `minloss_bruteforce.py` | the examples of the paper, and random instances against brute force |
| `closure_check.py`, `iconf_check.py`, `decomp4_check.py` | C against Python closures, the ports against the Java originals |
| `hardness_check.py`, `obstruction_stats.py` | the reduction of the hardness theorem for atomic covers, the bounds on every FD set |
| `paper_tables.py`, `paper_figures.py`, `embedded_loss.py`, `ablation.py` | the tables and figures |
| `run_*.sh`, `rerun_constants.sh`, `e1_relaunch.sh` | the server drivers of the final runs |

The remaining scripts are diagnostics, prototypes, and earlier MySQL variants of E3 that the paper does not report
(`e3.py`, `triggers.py`).

## Reproducing

```bash
python src/test_examples.py                          # the examples of the paper
python src/validate_fdlib.py 5 14400 32 300322       # logs/validate_n5f.log
python src/validate_fdlib.py 6 14400 31 73730        # logs/validate_n6e.log
python src/experiments.py                            # E1 and E2 (--one <set>, --table)
python src/meaningful.py                             # E1 on the meaningful FD sets
python src/gbcnf.py && python src/hybrid.py          # greedy BCNF decomposition, Opt and Hybrid
python src/e3pg.py --modes orig-x,3nf-x,3nfc-x,3nf,3nfc,keys,bcnf,gbcnf,repair,drop abalone   # E3
python src/e4.py abalone                             # E4
python src/weighted.py --budgets 1000000 abalone     # violation weights
python src/drift.py abalone                          # drift
python src/paper_tables.py && python src/paper_figures.py
```

Both validation runs pass: 300,322 random instances with five attributes and 73,730 with six.

## Protocol

### Platform

Every run is single-threaded on two AMD EPYC 7742 processors with 1 TB of main memory under Red Hat Enterprise
Linux 8.10 (`closure.c` with gcc 11.2, `-O3`). PostgreSQL 18.4 is built from source and initialised with
`initdb -E UTF8 --locale=C`; its configuration differs from the defaults in `shared_buffers = 32GB`,
`work_mem = 64MB`, `maintenance_work_mem = 2GB`, `max_locks_per_transaction = 4096`, `max_wal_size = 64GB`,
`checkpoint_timeout = 30min`, `autovacuum = off`, `jit = off` and `max_connections = 50`. The sessions of E3 set
`enable_seqscan = off` and `enable_bitmapscan = off`, so that the cached plans of the constraint checks do not depend
on the order of the measurements.

### Data

`data/fds/complete` and `data/fds/null-equality` hold the minimal FDs that HyFD discovers on the data sets of the
HPI repeatability benchmark (https://hpi.de/naumann/projects/repeatability/data-profiling/fds.html), under the null
equality interpretation for incomplete data; `data/fds/tpch` holds those of the eight TPC-H tables at scale factor
0.1. Attributes are column indices, which `src/fd_names.py` maps to names. The discovered sets are their own atomic
covers. `drop_constants.py` removes the constant attributes of echo, ncvoter, uniprot and TPC-H orders, since the
paper assumes that no attribute is constant; the discovered files remain in `data/fds/discovered/`.

The paper reports ten benchmark sets and TPC-H lineitem; `results/table_e12_full.tex` lists all 21 FD sets that we
computed. It leaves out the benchmark lineitem (the same picture as TPC-H lineitem), pdbx (3NF synthesis is in BCNF
already), diabetic and fd-red (3NF synthesis exceeds the budget), and the other TPC-H tables (loss zero for 3NF
synthesis). The source tables hold the distinct rows of the files: adult 32,537 of 32,561, breast 691 of 699,
letter 18,668 of 20,000, the others all. weather is the table `china_weather` of the iConf experiments (262,920 rows).

### E1 and E2

Every FD set has four hours for all algorithms together. A search that hits a budget or a cap reports its design as
unproved. Budgets are checked between the steps of a search, so running times exceed them on the largest sets.

| step | budget |
|---|---|
| `Drop`: exact search, budget b = 60 min on the whole schema | b, or b/2 if \|Σ_a\| > 200 |
| `Drop`: greedy, if the exact search does not finish | until 1.5 b |
| `Drop`: `Ascend` from the obstruction design and from the greedy design | 15 min each |
| `Repair`: `Drop` on a critical schema, without `Ascend` | b = 5 min each |
| `Repair`: ascents after the assembly | 15 min each |
| `Repair` fallback: greedy on Γ⁺, then `Drop` | 30 min, b = 30 min |
| `Repair` fallback: ascents from the obstruction designs of (R, Γ⁺) and (R, Σ) | 15 min each |

- `Drop` enumerates at most four weakened FDs per candidate, and on schemata with more than twelve attributes only
  those that add at most three attributes to a left-hand side. On FD sets with thousands of minimal FDs its greedy
  exceeds the budget, and the ascent starts from the obstruction design alone, with 30 min.
- `Ascend` examines candidates with at most 14 attributes in their schema. A climb accepts at most 50 exchanges of
  equal loss in a row, a kick makes a random exchange or removes up to four random elements, and a run ends after 20
  kicks without improvement. The deterministic run is followed by up to 60 runs in random order.
- Ties between designs of least loss go to fewer equivalence classes of left-hand sides (`Ascend`) and to fewer
  schemata (`Repair`, `Drop`); a tie-break never trades loss for schemata.
- Hybrid takes the level of X as the largest number of records of the source table that agree on X (1 for a
  superkey). Without data, the level is 1 for a superkey and unbounded otherwise; the paper marks these runs.

### Meaningful FD sets

`meaningful.py` lists the FDs by attribute name with their sources and writes them to `data/fds/meaningful/`.

- **food** (17 attributes): the FDs of the Chicago food inspections in HoloClean (Rekatsinas et al., PVLDB 2017,
  Fig. 1 and Sec. 6.1) and the key InspectionID.
- **price paid** (16): the UK Price Paid Data with the address rules of the Royal Mail PAF Programmers' Guide
  (Edition 7, Version 6, pp. 14 and 17) and the key TransactionID.
- **hospital** (19): the nine denial constraints of HoloClean on its hospital data as FDs, ProviderNumber → the
  hospital attributes, ProviderNumber, MeasureCode → Score, Sample, and the address rule of food.
- **TPC-DS** (95): store_sales joined with item, store and date_dim without their validity columns, with the keys,
  the rule of historical dimensions (Clause 1.3.3 of v4.0.0) and ss_ticket_number → d_date_sk, s_store_sk.

In the E1 records these sets are `food+c1`, `uk`, `hospital` and `tpcds`; the other entries are variants that add or
remove FDs of doubtful status. E3 and E4 run on them as `food`, `pricepaid`, `hospital` and `tpcds`.

`documented.py` prepares the data from downloads of 14 October 2026, which are not in the repository: the Food
Inspections of the City of Chicago (data set 4ijn-s7e5), the Price Paid Data of 2024 (contains HM Land Registry data
© Crown copyright and database right 2024, licensed under the Open Government Licence v3.0), the clean hospital data
of Raha (github.com/BigDaMa/raha), and TPC-DS at scale factor 1 from `dsdgen` of tpcds-kit (commit 5a3a817, built
with `make OS=LINUX CC="gcc -fcommon"`). It normalises the values, removes duplicates and, until every FD holds, the records that
disagree with the most frequent right-hand side of their group. It keeps 276,716 records of food (87.3%), 926,485
of price paid (99.5%), all 1,000 of hospital and the 2,685,687 sales of TPC-DS that have an item, a store and a date.

### E3: insertion times

Every design gets one table per schema with the distinct projection of the data, a `UNIQUE` constraint per declared
key, and, on the original relation and on the critical schemata of 3NF synthesis, an exclusion constraint
`EXCLUDE USING gist (X WITH =, A WITH <>)` per non-key FD X → A of a minimal cover. Values are stored as text, so a
missing value is a value of its own, as under the null equality interpretation.

A synthetic record copies a random stored record on a closed set of attributes and has fresh values elsewhere, so it
satisfies Σ while the exclusion constraints still meet the copied group. The 10,000, 20,000 and 30,000 records are
generated before the clock starts and inserted in one transaction with one `INSERT ... ON CONFLICT DO NOTHING` per
table and batch of 1,000; the commit is timed. Times are means of five repetitions, each on rebuilt tables (weather
and TPC-DS from file copies of prewarmed templates, `--copy`), with a watchdog after two hours of insertion time.

`teaser_pg.py` measures the running example on an address book of 100,000 customers in 200 towns with ten zip codes
each, where half of the inserted customers move to an existing address. `concurrency_check.py` confirms that an
exclusion constraint rejects the second of two concurrent conflicting insertions under every isolation level, while
a trigger admits both under `READ COMMITTED` and `REPEATABLE READ`. `conc.py` (`run_conc.sh`) measures throughput
with up to 32 concurrent clients; the paper does not report it.

### E4: integrity risk, violation weights and drift

- An update replaces the value of a random attribute in a random record by its value in another random record, and
  is evaluated on its own against the stored relation. It is harmful if it violates an FD of Σ, and a design catches
  it if it violates a declared key. The integrity risk is the share of harmful updates missed, averaged over
  seeds 1 to 5 with 10,000 updates each. 3NF synthesis enters with its non-key FDs left to the application, and the
  original relation with every FD enforced has risk zero.
- The violation weight of a minimal FD is one plus the number of updates of seeds 6 to 10 that violate it.
  `Repair` and `Drop` run with the budgets of E1, and `--budgets 1000000` lets the iterative deepening of `Drop` use
  every subset sum of the weights. All designs are evaluated on the updates of seeds 1 to 5.
- Under drift, the attribute of an update follows (1 − α)·uniform + α·Zipf(s) over a random permutation of the
  non-constant attributes, for s ∈ {1, 2} and α ∈ {0.25, 0.5, 0.75, 1}, with ten permutations of 10,000 updates each.
