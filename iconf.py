r"""iconf.py: the 3NF synthesis iCONF of Zhang and Link (SIGMOD 2025), run through its Java implementation.

iconf_decomposition(n, Da) writes the atomic cover Da to a file, runs iconf/IConfDriver.java (which calls
iCONF.exe_decomp with optimization target FDN and the reduced minimal key/FD cover) and returns the schemata.
The Java class path is taken from the environment variable ICONF_CP, else iconf/build/classes together with
iconf/build/fastjson-1.2.79.jar; iconf/README.md says how to build them from the iCONF sources.
"""
import os, subprocess, tempfile
from fdlib import bits

HERE = os.path.dirname(os.path.abspath(__file__))

def classpath():
    cp = os.environ.get("ICONF_CP")
    if cp:
        return cp
    b = os.path.join(HERE, "iconf", "build")
    return os.pathsep.join([os.path.join(b, "classes"), os.path.join(b, "fastjson-1.2.79.jar")])

def iconf_decomposition(n, Da, timeout=None, java="java"):
    """the schemata (bitmasks) that iCONF returns on the atomic cover Da over n attributes, and the running time
    of iCONF itself in seconds (without the JVM start and the file transfer)"""
    with tempfile.TemporaryDirectory() as d:
        fin, fout = os.path.join(d, "fds.txt"), os.path.join(d, "out.txt")
        with open(fin, "w") as f:
            for X, A in Da.fds:
                f.write("%s -> %d\n" % (" ".join(str(a) for a in bits(X)), A))
        subprocess.run([java, "-cp", classpath(), "IConfDriver", fin, str(n), fout], check=True, timeout=timeout,
                       stdout=subprocess.DEVNULL)
        dec, t = [], None
        for line in open(fout):
            if line.startswith("# time_ms"):
                t = int(line.split()[2]) / 1000.0
                continue
            S = 0
            for a in line.split():
                S |= 1 << int(a)
            if S:
                dec.append(S)
    return dec, t
