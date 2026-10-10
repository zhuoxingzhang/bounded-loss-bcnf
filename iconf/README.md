# iCONF

`IConfDriver.java` runs the 3NF synthesis iCONF of Zhang and Link (SIGMOD 2025) on an atomic cover and
writes its schemata; `../iconf.py` calls it from Python. The iCONF sources are not part of this repository.
To build, copy the directories `nf`, `object` and `util` of the iCONF sources to `build/src` and its
`fastjson-1.2.79.jar` to `build`, then compile for Java 8:

    sed -i 's/getFreeMemorySize()/getFreePhysicalMemorySize()/g' build/src/util/Utils.java   # Java 8 API, memory statistics only
    find build/src -name "*.java" | grep -v DBUtils > build/sources.txt
    echo IConfDriver.java >> build/sources.txt
    javac --release 8 -nowarn -cp build/fastjson-1.2.79.jar -d build/classes @build/sources.txt

`build/` is ignored by git.
