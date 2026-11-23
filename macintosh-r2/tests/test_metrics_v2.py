"""Deterministic R2 host regression. Requires already-built host executable.
The QNX target binary is tested separately with Step9_Validate_R2_QNX.py.
"""
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXE = ROOT / "build" / "trace_metrics_v2_host.exe"
CFG = ROOT / "fixtures" / "config.csv"

def rows(stdout, prefix):
    result = []
    for line in stdout.splitlines():
        if line.startswith(prefix + ","):
            result.append(dict(k.split("=", 1) for k in line.split(",")[1:]))
    return result

def execute(fixture, config=CFG, window=100):
    return subprocess.run([str(EXE), str(config), str(ROOT / "fixtures" / fixture),
                           str(window)], capture_output=True, text=True, timeout=5)

class MetricsV2Tests(unittest.TestCase):
    def test_compile_artifact_exists(self):
        self.assertTrue(EXE.is_file())

    def test_nested_isr_exclusive(self):
        r = execute("r2_nested_gap.csv")
        self.assertEqual(r.returncode, 0, r.stderr)
        by_id = {int(x["id"]): x for x in rows(r.stdout, "M2_ISR_SUMMARY")}
        self.assertEqual(by_id[1]["inclusive_us"], "100")
        self.assertEqual(by_id[1]["exclusive_us"], "70")
        self.assertEqual(by_id[2]["exclusive_us"], "30")

    def test_no_fabricated_idle_or_cpu_overlap(self):
        r = execute("r2_nested_gap.csv")
        s = rows(r.stdout, "M2_SESSION")[0]
        self.assertEqual((s["elapsed_us"], s["task_us"], s["isr_us"],
                          s["idle_us"], s["unknown_us"]), ("700", "350", "100", "0", "250"))
        self.assertEqual(sum(int(s[x]) for x in
                             ("task_us", "isr_us", "idle_us", "unknown_us")), 700)

    def test_sliding_windows(self):
        r = execute("r2_nested_gap.csv")
        w = rows(r.stdout, "M2_WINDOW")
        self.assertEqual(len(w), 7)
        self.assertEqual((w[1]["start_us"], w[1]["end_us"], w[1]["isr_us"]),
                         ("100", "200", "100"))
        self.assertEqual((w[4]["task_us"], w[4]["unknown_us"]), ("50", "50"))
        self.assertEqual(w[5]["quality"], "GAP")
        for b in w:
            self.assertEqual(sum(int(b[k]) for k in
                             ("task_us", "isr_us", "idle_us", "unknown_us")),
                             int(b["elapsed_us"]))

    def test_explicit_idle_only(self):
        r = execute("r2_idle.csv", ROOT / "fixtures" / "r2_idle_config.csv")
        self.assertEqual(r.returncode, 0, r.stderr)
        s = rows(r.stdout, "M2_SESSION")[0]
        self.assertEqual((s["task_us"], s["idle_us"], s["unknown_us"]),
                         ("60", "40", "0"))
        self.assertEqual(s["quality"], "COMPLETE")

    def test_task_exclusive_per_window(self):
        r = execute("r2_nested_gap.csv")
        t = rows(r.stdout, "M2_WINDOW_TASK")
        self.assertEqual(sum(int(x["exclusive_us"]) for x in t if x["id"]=="1"),300)
        self.assertEqual(sum(int(x["exclusive_us"]) for x in t if x["id"]=="2"),50)

    def test_unmatched_isr_exit_invalidates(self):
        r = execute("r2_bad_isr.csv")
        self.assertNotEqual(r.returncode,0)
        self.assertIn("code=UNMATCHED_ISR_EXIT",r.stdout)
        s = rows(r.stdout,"M2_ISR_SUMMARY")[0]
        self.assertEqual(s["incomplete"],"1")

    def test_time_reversal_is_error(self):
        r=execute("r2_reversal.csv")
        self.assertEqual(r.returncode,1)
        self.assertIn("NON_MONOTONIC_TIMESTAMP",r.stdout)
        self.assertEqual(rows(r.stdout,"M2_SESSION")[0]["quality"],"ERROR")

    def test_switch_without_release_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            f=Path(td)/"unreleased.csv"
            f.write_text("0,SWITCH_IN,1\n100,SWITCH_OUT,1\n",encoding="ascii")
            r=subprocess.run([str(EXE),str(CFG),str(f),"100"],capture_output=True,text=True)
            self.assertEqual(r.returncode,1)
            self.assertIn("INVALID_SWITCH_IN",r.stdout)
            self.assertEqual(rows(r.stdout,"M2_SESSION")[0]["unknown_us"],"100")

    def test_window_limit_input_rejected(self):
        r=execute("r2_idle.csv",ROOT / "fixtures" / "r2_idle_config.csv",0)
        self.assertEqual(r.returncode,2)

    def test_qnx_source_independent_of_original_R1(self):
        self.assertTrue((ROOT/"src"/"trace_engine.c").is_file())
        self.assertTrue((ROOT/"include"/"trace_engine.h").is_file())
        self.assertTrue((ROOT/"src"/"trace_metrics_v2.c").is_file())
        # Native QNX binary is built separately; host tests must not assume one exists.

if __name__=="__main__":
    unittest.main()
