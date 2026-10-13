r"""meaningful.py: the losses of all designs on FD sets whose FDs are documented business rules rather than
discovered from data: Chicago Food Inspections (HoloClean), UK Price Paid Data (Royal Mail PAF rules), Hospital
(HoloClean/Raha with the address rule of Food) and TPC-DS store sales joined with its historical (type-2) dimensions.

Every set lists its FDs by attribute name; the sources are in the comments. Variants add or remove the FDs whose
status is doubtful. For every set the script computes the atomic cover Sigma_a and the designs of E1 (key-only,
iCONF, the classical 3NF synthesis, the classical and the greedy BCNF decomposition, Hybrid without cardinality
constraints, Repair, Drop) with their losses, the lost FDs by name, soundness and local enforcement.

usage: python3 meaningful.py --write                   write the FD sets to data/fds/meaningful/<name>.json
       python3 meaningful.py [--parallel K] [name ...] every set in its own process (records in
                                                       results/meaningful_<name>.jsonl)
       python3 meaningful.py --one <name>              one set
       python3 meaningful.py --table                   the table of the records
       python3 meaningful.py --tex                     the rows of the sets in the paper, in the columns of Tab. e12
"""
import sys, os, json, time, traceback
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fdlib import *
from drop import drop
from repair import repair
from iconf import iconf_decomposition
import hybrid as hyb
from experiments import LOCAL_TIME, DROP_TIME, ASCEND_TIME, MAX_W, MAX_MINIMAL, max_extra_for, design_json

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "data", "fds", "meaningful")
TIMEOUT = 14400

# ----------------------------------------------------------------------------- the FD sets

FOOD = ["InspectionID", "DBAName", "AKAName", "License", "FacilityType", "Risk", "Address", "City", "State", "Zip",
        "InspectionDate", "InspectionType", "Results", "Violations", "Latitude", "Longitude", "Location"]
# Rekatsinas et al., HoloClean, PVLDB 10(11) 2017, Fig. 1: c1 DBAName -> Zip, c2 Zip -> City, State,
# c3 City, State, Address -> Zip; Sec. 6.1 (prose): conflicting zips, results and facility types of one establishment
FOOD_FDS = [(["InspectionID"], [a for a in FOOD if a != "InspectionID"]),
            (["Zip"], ["City", "State"]),
            (["City", "State", "Address"], ["Zip"]),
            (["License"], ["Zip", "FacilityType"]),
            (["License", "InspectionDate"], ["Results"])]

UK = ["TransactionID", "Price", "Date", "Postcode", "PropertyType", "OldNew", "Duration", "PAON", "SAON", "Street",
      "Locality", "Town", "District", "County", "PPDCategory", "RecordStatus"]
# Royal Mail, PAF Programmers' Guide, Ed. 7 v6.2: one postcode per delivery point, one locality, post town and
# thoroughfare per postcode; Street = Thoroughfare, Locality = Dependent Locality, Town = Post Town
UK_FDS = [(["TransactionID"], [a for a in UK if a != "TransactionID"]),
          (["PAON", "SAON", "Street", "Locality", "Town"], ["Postcode"]),
          (["Postcode"], ["Street", "Locality", "Town"])]

HOSP = ["ProviderNumber", "HospitalName", "Address1", "Address2", "Address3", "City", "State", "ZipCode",
        "CountyName", "PhoneNumber", "HospitalType", "HospitalOwner", "EmergencyService", "Condition", "MeasureCode",
        "MeasureName", "Score", "Sample", "Stateavg"]
HOSP_ATTRS = HOSP[1:13]
# (a) the 9 DCs of HoloClean (PVLDB 2017) and Llunatic, the keys of the hospital and of the measurement, and the
# address rule c3 of Food on the identical address columns
HOSP_FDS = [(["ZipCode"], ["City", "State"]),
            (["PhoneNumber"], ["ZipCode", "City", "State"]),
            (["ProviderNumber", "MeasureCode"], ["Stateavg"]),
            (["MeasureCode"], ["MeasureName", "Condition"]),
            (["State", "MeasureCode"], ["Stateavg"]),
            (["ProviderNumber"], HOSP_ATTRS),
            (["ProviderNumber", "MeasureCode"], ["Score", "Sample"]),
            (["Address1", "City", "State"], ["ZipCode"])]
# the union with the lists (b) HoloClean repository, (c) QCRI gold, (d) Raha and (e) Martin et al. (PVLDB 2025),
# without the FDs that fail on the clean data or relate unrelated facts (MeasureCode -> Stateavg, City -> ZipCode,
# Condition, MeasureName -> HospitalType, ZipCode -> EmergencyService)
HOSP_ALL = HOSP_FDS + [(["HospitalName"], ["ZipCode", "PhoneNumber", "Address1", "HospitalOwner", "ProviderNumber",
                                           "City", "HospitalType"]),
                       (["MeasureName"], ["MeasureCode", "Condition"]),
                       (["City"], ["CountyName"]),
                       (["ZipCode"], ["CountyName"]),
                       (["CountyName"], ["State"]),
                       (["PhoneNumber"], ["HospitalType", "CountyName"]),
                       (["PhoneNumber", "HospitalOwner"], ["HospitalName", "ProviderNumber"]),
                       (["HospitalName", "CountyName"], ["HospitalOwner", "City", "ZipCode", "ProviderNumber",
                                                         "PhoneNumber"]),
                       (["HospitalName", "City"], ["ZipCode", "ProviderNumber", "PhoneNumber"])]

# TPC-DS v4.0.0: store_sales joined with item, store and date_dim on the surrogate keys, without the validity columns
# *_rec_start_date and *_rec_end_date; Clause 1.3.3: a sale refers to the revision of the item (store) that was
# active on its date, so i_item_id, d_date -> i_item_sk and s_store_id, d_date -> s_store_sk; the generator draws
# the date and the store once per ticket (w_store_sales.c, mk_master)
SS = ["ss_sold_time_sk", "ss_customer_sk", "ss_cdemo_sk", "ss_hdemo_sk", "ss_addr_sk", "ss_promo_sk",
      "ss_ticket_number", "ss_quantity", "ss_wholesale_cost", "ss_list_price", "ss_sales_price", "ss_ext_discount_amt",
      "ss_ext_sales_price", "ss_ext_wholesale_cost", "ss_ext_list_price", "ss_ext_tax", "ss_coupon_amt", "ss_net_paid",
      "ss_net_paid_inc_tax", "ss_net_profit"]
ITEM = ["i_item_sk", "i_item_id", "i_item_desc", "i_current_price", "i_wholesale_cost", "i_brand_id", "i_brand",
        "i_class_id", "i_class", "i_category_id", "i_category", "i_manufact_id", "i_manufact", "i_size",
        "i_formulation", "i_color", "i_units", "i_container", "i_manager_id", "i_product_name"]
STORE = ["s_store_sk", "s_store_id", "s_closed_date_sk", "s_store_name", "s_number_employees", "s_floor_space",
         "s_hours", "s_manager", "s_market_id", "s_geography_class", "s_market_desc", "s_market_manager",
         "s_division_id", "s_division_name", "s_company_id", "s_company_name", "s_street_number", "s_street_name",
         "s_street_type", "s_suite_number", "s_city", "s_county", "s_state", "s_zip", "s_country", "s_gmt_offset",
         "s_tax_precentage"]
DATE = ["d_date_sk", "d_date_id", "d_date", "d_month_seq", "d_week_seq", "d_quarter_seq", "d_year", "d_dow", "d_moy",
        "d_dom", "d_qoy", "d_fy_year", "d_fy_quarter_seq", "d_fy_week_seq", "d_day_name", "d_quarter_name",
        "d_holiday", "d_weekend", "d_following_holiday", "d_first_dom", "d_last_dom", "d_same_day_ly",
        "d_same_day_lq", "d_current_day", "d_current_week", "d_current_month", "d_current_quarter", "d_current_year"]

def tpcds(ss, item, store, date):
    names = ss + item + store + date
    fds = [(["i_item_sk"], item[1:]), (["s_store_sk"], store[1:]), (["d_date_sk"], date[1:]),
           (["d_date"], ["d_date_sk"]),
           (["i_item_sk", "ss_ticket_number"], [a for a in ss if a != "ss_ticket_number"]),
           (["ss_ticket_number"], ["d_date_sk", "s_store_sk"]),
           (["i_item_id", "d_date"], ["i_item_sk"]),
           (["s_store_id", "d_date"], ["s_store_sk"])]
    if "d_date_id" in date:
        fds.append((["d_date_id"], ["d_date_sk"]))
    return names, fds

SETS = {
    "food": (FOOD, FOOD_FDS),
    "food+c1": (FOOD, FOOD_FDS + [(["DBAName"], ["Zip"])]),
    "uk": (UK, UK_FDS),
    "uk+admin": (UK, UK_FDS + [(["Postcode"], ["District"]), (["District"], ["County"])]),
    "hospital": (HOSP, HOSP_FDS),
    "hospital-all": (HOSP, HOSP_ALL),
    "tpcds-core": tpcds(["ss_ticket_number", "ss_quantity", "ss_sales_price"],
                        ["i_item_sk", "i_item_id", "i_item_desc", "i_current_price"],
                        ["s_store_sk", "s_store_id", "s_store_name"], ["d_date_sk", "d_date"]),
    "tpcds": tpcds(SS, ITEM, STORE, DATE),
}

def fdset(name):
    names, fds = SETS[name]
    idx = {a: i for i, a in enumerate(names)}
    assert len(idx) == len(names), name
    F = []
    for lhs, rhs in fds:
        L = mask([idx[a] for a in lhs])
        F.extend((L, idx[a]) for a in rhs if a not in lhs)
    return names, FDSet(len(names), F)

def write():
    os.makedirs(OUT, exist_ok=True)
    for name, (names, fds) in SETS.items():
        idx = {a: i for i, a in enumerate(names)}
        d = {"R": len(names), "names": names,
             "fds": [{"lhs": [idx[a] for a in l], "rhs": [idx[a] for a in r]} for l, r in fds]}
        with open(os.path.join(OUT, name + ".json"), "w", encoding="utf-8") as f:
            json.dump(d, f, indent=1)
    print("wrote", len(SETS), "sets to", OUT)

# ----------------------------------------------------------------------------- the designs

def fd_str(names, f):
    X, A = f
    return ",".join(names[a] for a in bits(X)) + "->" + names[A]

def measure(names, Da, des, chase=True):
    n = len(names)
    E = key_dependencies(n, des)
    lost = unenforced(Da, E)
    schemata = [S for S, _ in des]
    try:
        sound = chase_lossless(n, schemata, E) if chase and len(schemata) <= 40 else None
    except Exception:
        sound = None
    try:
        local = is_locally_enforced(des, atomic_cover(E, cap=MAX_MINIMAL))
    except CapExceeded:
        local = None
    return {"loss": len(lost), "lost": [fd_str(names, f) for f in lost], "schemata": len(des),
            "bcnf": all(is_bcnf(Da, S) for S in schemata), "sound": sound, "local": local,
            "design": [[[names[a] for a in bits(S)], [[names[a] for a in bits(K)] for K in keys]] for S, keys in des]}

def run(name):
    names, F = fdset(name)
    n = len(names)
    rec = {"name": name, "n": n, "fds": len(F)}
    t0 = time.time()
    Da = atomic_cover(F, cap=MAX_MINIMAL)
    R = (1 << n) - 1
    rec["minimal_fds"] = len(Da)
    rec["keys"] = [[names[a] for a in bits(K)] for K in minimal_keys(Da, R)]
    unc, crit = split_critical(Da)
    rec["critical_minimal_fds"] = [fd_str(names, f) for f in crit]
    U = FDSet(n, unc)
    rec["obstructions"] = sum(1 for g in crit if not U.implies(g[0], g[1]))
    rec["enforceable"] = enforceable(Da)[0]
    rec["time_cover"] = round(time.time() - t0, 1)
    D = {}
    D["key-only"] = measure(names, Da, [(R, minimal_keys(Da, R))])
    rec["nu"] = D["key-only"]["loss"]
    dec = iconf_decomposition(n, Da)
    rec["iconf_critical_schemata"] = sum(1 for S in dec if not is_bcnf(Da, S))
    D["iconf"] = measure(names, Da, keyed(Da, dec))
    D["3nf-classical"] = measure(names, Da, keyed(Da, synthesize_3nf(F, Da)))
    D["bcnf-classical"] = measure(names, Da, keyed(Da, bcnf_decomposition(Da)))
    gdec, st = greedy_bcnf_decomposition(Da, time_limit=1800)
    D["bcnf-greedy"] = measure(names, Da, keyed(Da, gdec))
    D["bcnf-greedy"]["timed_out"] = st["timed_out"]
    hdec, _ = hyb.hybrid(Da, hyb.levels_from_fds(Da))
    D["hybrid"] = measure(names, Da, keyed(Da, [S for S, _ in hdec]))
    t1 = time.time()
    rr = repair(n, F, Da=Da, local_time_limit=LOCAL_TIME, time_limit=DROP_TIME, max_w=MAX_W,
                max_extra=max_extra_for(n), ascend_time=ASCEND_TIME, dec0=dec)
    if rr.design is not None:
        D["repair"] = measure(names, Da, rr.design)
        D["repair"].update(mode=rr.mode, exact=rr.exact, time=round(time.time() - t1, 1))
    t1 = time.time()
    dr = drop(n, Da, time_limit=DROP_TIME, max_w=MAX_W, max_extra=max_extra_for(n), ascend_time=ASCEND_TIME)
    if dr.design is not None:
        D["drop"] = measure(names, Da, dr.design)
        D["drop"].update(lower_bound=dr.lower_bound, exact=dr.exact, time=round(time.time() - t1, 1))
    rec["designs"] = D
    rec["lambda"] = dr.loss if dr.exact else None
    rec["time_total"] = round(time.time() - t0, 1)
    return rec

def run_one(name):
    try:
        rec = run(name)
    except Exception:
        rec = {"name": name, "error": traceback.format_exc()[-800:]}
    with open(os.path.join(ROOT, "results", "meaningful_%s.jsonl" % name), "w", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")
    summary(rec)

ORDER = ["key-only", "iconf", "3nf-classical", "bcnf-classical", "bcnf-greedy", "hybrid", "repair", "drop"]

def summary(rec):
    if "error" in rec:
        print(rec["name"], "ERROR", rec["error"], flush=True)
        return
    print("%s: n=%d |Sigma|=%d |Sigma_a|=%d lambda=%s keys=%s" % (rec["name"], rec["n"], rec["fds"],
          rec["minimal_fds"], rec["lambda"], rec["keys"]), flush=True)
    for k in ORDER:
        d = rec["designs"].get(k)
        if d is None:
            continue
        flags = ("BCNF" if d["bcnf"] else "3NF") + ("" if d["sound"] is not False else " UNSOUND") + \
                ("" if d["local"] is not False else " not-local")
        print("   %-15s loss %4d  %2d schemata  %-20s lost %s" % (k, d["loss"], d["schemata"], flags,
              "; ".join(d["lost"][:6]) + (" ..." if len(d["lost"]) > 6 else "")), flush=True)

def table():
    for name in SETS:
        f = os.path.join(ROOT, "results", "meaningful_%s.jsonl" % name)
        if os.path.isfile(f):
            for line in open(f, encoding="utf-8"):
                if line.strip():
                    summary(json.loads(line))

PAPER = [("food+c1", "food"), ("uk", "price paid"), ("hospital", "hospital"), ("tpcds", "TPC-DS")]

def tex_rows():
    """rows in the columns of Tab. e12 (records, |R|, |Sigma_a|, keys, crit., nu, |O|, the eight losses, bound,
    schemata of iCONF and Repair, times of Repair and Drop); dagger: unsound, double dagger: Hybrid without data"""
    def cell(d):
        return "{:,}".format(d["loss"]) + ("" if d["sound"] is not False else r"$^{\dagger}$")
    def secs(x):
        return "0.0" if x < 0.05 else ("%.1f" % x if x < 100 else "{:,}".format(int(round(x))))
    for name, label in PAPER:
        r = json.loads(open(os.path.join(ROOT, "results", "meaningful_%s.jsonl" % name), encoding="utf-8").readline())
        D = r["designs"]
        print(" & ".join([label, "--", str(r["n"]), "{:,}".format(r["minimal_fds"]), str(len(r["keys"])),
                          str(r["iconf_critical_schemata"]), "{:,}".format(r["nu"]), str(r["obstructions"]),
                          cell(D["iconf"]), cell(D["3nf-classical"]), cell(D["bcnf-classical"]), cell(D["bcnf-greedy"]),
                          cell(D["hybrid"]) + r"$^{\ddagger}$", cell(D["repair"]), cell(D["drop"]),
                          str(D["drop"]["lower_bound"]), str(D["iconf"]["schemata"]), str(D["repair"]["schemata"]),
                          secs(D["repair"]["time"]), secs(D["drop"]["time"])]) + r"\\")

DATA = {"food+c1": "food", "uk": "pricepaid", "hospital": "hospital"}   # the sets with data (documented.py)

def tex_documented():
    """rows of the paper's table of documented FDs (the records kept by documented.py, |R|, |Sigma_a|, nu, losses of
    iCONF, classical 3NF synthesis, classical and greedy BCNF decomposition, Repair and Drop); dagger: unsound"""
    def cell(d):
        return "{:,}".format(d["loss"]) + ("" if d["sound"] is not False else r"$^{\dagger}$")
    def records(name):
        f = os.path.join(ROOT, "results", "documented_%s.json" % DATA.get(name, ""))
        return "{:,}".format(json.load(open(f, encoding="utf-8"))["kept"]) if os.path.isfile(f) else "--"
    for name, label in PAPER:
        r = json.loads(open(os.path.join(ROOT, "results", "meaningful_%s.jsonl" % name), encoding="utf-8").readline())
        D = r["designs"]
        print(" & ".join([label, records(name), str(r["n"]), "{:,}".format(r["minimal_fds"]), "{:,}".format(r["nu"])]
                         + [cell(D[a]) for a in ("iconf", "3nf-classical", "bcnf-classical", "bcnf-greedy", "repair", "drop")])
              + r"\\")

def main():
    import subprocess
    args = sys.argv[1:]
    os.makedirs(os.path.join(ROOT, "results"), exist_ok=True)
    if args[:1] == ["--write"]:
        write()
        return
    if args[:1] == ["--tex"]:
        tex_documented()
        return
    if args[:1] == ["--tex-e12"]:
        tex_rows()
        return
    if args[:1] == ["--one"]:
        run_one(args[1])
        return
    if args[:1] == ["--table"]:
        table()
        return
    parallel = 1
    if args[:1] == ["--parallel"]:
        parallel = int(args[1])
        args = args[2:]
    names = args or list(SETS)
    procs = []
    for name in names:
        while len([p for p in procs if p.poll() is None]) >= parallel:
            time.sleep(5)
        procs.append(subprocess.Popen([sys.executable, os.path.abspath(__file__), "--one", name]))
    t0 = time.time()
    for p in procs:
        try:
            p.wait(timeout=max(1, TIMEOUT - (time.time() - t0)))
        except subprocess.TimeoutExpired:
            p.kill()
    print("done", flush=True)

if __name__ == "__main__":
    main()
