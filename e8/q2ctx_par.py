"""The masks of q2ctx.py that a log of it does not list yet, on more workers (same jobs, same output lines).
usage: python q2ctx_par.py <dir of q2ctx.py> <contexts> <log of the earlier run> <workers>"""
import sys, ast
src = open(sys.argv[1] + "/q2ctx.py", encoding="utf-8").read()
exec(src.split('if __name__=="__main__":')[0])
if __name__ == "__main__":
    done = set()
    for line in open(sys.argv[3], encoding="utf-8"):
        if line.startswith("["):
            fds = ast.literal_eval(line[:line.index("]") + 1])
            done.add(sum(1 << base.index(f) for f in fds))
    rest = [m for m in range(64) if m not in done]
    print("# %d masks done in the earlier run, %d to go" % (len(done), len(rest)), flush=True)
    with Pool(int(sys.argv[4])) as p:
        for r in p.imap_unordered(job, rest):
            m = r[0]; flag = "  <== local>full" if len(r) > 4 and r[2] is not None and r[4] != r[2] else ""
            print([base[j] for j in range(6) if (m >> j) & 1], r[1:], flag, flush=True)
