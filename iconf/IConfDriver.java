import java.io.BufferedReader;
import java.io.FileReader;
import java.io.FileWriter;
import java.io.OutputStream;
import java.io.PrintStream;
import java.io.PrintWriter;
import java.util.ArrayList;
import java.util.List;

import nf.iCONF;
import object.DataTypeEnum;
import object.Dataset;
import object.FD;
import object.Parameter;
import object.Schema;

/**
 * Runs the 3NF synthesis iCONF of Zhang and Link (SIGMOD 2025) on an atomic cover and writes its schemata.
 *
 * usage: java -cp <iCONF classes>:<fastjson jar>:. IConfDriver <fd file> <number of attributes> <output file>
 *
 * The FD file holds one minimal FD per line, "a b c -> d" with attribute indices 0..n-1 (an empty left-hand
 * side is allowed). The output file holds "# time_ms <t>" and then one schema per line as attribute indices.
 * The decomposition is the one of iCONF.exe_decomp with optimization target FDN and the reduced minimal
 * key/FD cover, as in the experiments of the iCONF paper.
 */
public class IConfDriver {
	public static void main(String[] args) throws Exception {
		List<FD> atomic = new ArrayList<FD>();
		BufferedReader br = new BufferedReader(new FileReader(args[0]));
		String line;
		while ((line = br.readLine()) != null) {
			line = line.trim();
			if (line.isEmpty() || line.startsWith("#"))
				continue;
			String[] parts = line.split("->");
			List<String> lhs = new ArrayList<String>();
			for (String t : parts[0].trim().split("\\s+"))
				if (!t.isEmpty())
					lhs.add(t);
			List<String> rhs = new ArrayList<String>();
			rhs.add(parts[1].trim());
			atomic.add(new FD(lhs, rhs));
		}
		br.close();
		int n = Integer.parseInt(args[1]);
		List<String> R = new ArrayList<String>();
		for (int i = 0; i < n; i++)
			R.add(i + "");
		Parameter para = new Parameter();
		para.dataset = new Dataset(args[0], n, 0, ",", "", DataTypeEnum.COMPLETE);
		para.fd_add = args[0];
		PrintStream out = System.out;
		System.setOut(new PrintStream(new OutputStream() {
			public void write(int b) {
			}
		}));
		long t0 = System.currentTimeMillis();
		List<Schema> D = new iCONF().exe_decomp("FDN", para, "reduced minimal keyfd", R, atomic);
		long t1 = System.currentTimeMillis();
		System.setOut(out);
		PrintWriter pw = new PrintWriter(new FileWriter(args[2]));
		pw.println("# time_ms " + (t1 - t0));
		for (Schema s : D) {
			StringBuilder sb = new StringBuilder();
			for (String a : s.getAttr_set()) {
				if (sb.length() > 0)
					sb.append(' ');
				sb.append(a);
			}
			pw.println(sb.toString());
		}
		pw.close();
	}
}
