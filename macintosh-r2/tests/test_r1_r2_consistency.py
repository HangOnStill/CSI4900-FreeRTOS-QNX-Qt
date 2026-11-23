"""Cross-check R1 activation metrics and R2 exclusive occupancy on same fixture."""
import subprocess
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
R1=ROOT/"build"/"trace_analyzer_host.exe"
R2=ROOT/"build"/"trace_metrics_v2_host.exe"
CFG=ROOT/"fixtures"/"config.csv"
def run(exe,fixture):
    args=[str(exe),str(CFG),str(ROOT/"fixtures"/fixture)]
    if exe==R2:args.append("10000")
    return subprocess.run(args,capture_output=True,text=True,timeout=8)
def row(text,prefix):
    return next(x for x in text.splitlines() if x.startswith(prefix))
def fields(line):
    return dict(x.split("=",1) for x in line.split(",")[1:])
class R1R2Consistency(unittest.TestCase):
    def test_normal_cpu_equal(self):
        a=run(R1,"normal.csv");b=run(R2,"normal.csv")
        self.assertEqual(a.returncode,0)
        self.assertEqual(b.returncode,0)
        old=fields(row(a.stdout,"TASK_SUMMARY,id=1"))
        new=fields(row(b.stdout,"M2_TASK_SUMMARY,id=1"))
        self.assertEqual(old["cpu_us"],"6000")
        self.assertEqual(new["exclusive_us"],old["cpu_us"])
        self.assertEqual(fields(row(b.stdout,"M2_SESSION"))["isr_us"],"200")
    def test_blocking_cpu_equal_and_unknown_not_idle(self):
        a=run(R1,"blocking.csv");b=run(R2,"blocking.csv")
        self.assertEqual(a.returncode,0)
        self.assertEqual(b.returncode,0)
        self.assertEqual(fields(row(a.stdout,"TASK_SUMMARY,id=1"))["cpu_us"],"600")
        self.assertEqual(fields(row(b.stdout,"M2_TASK_SUMMARY,id=1"))["exclusive_us"],"600")
        s=fields(row(b.stdout,"M2_SESSION"))
        self.assertEqual(s["idle_us"],"0")
        self.assertGreater(int(s["unknown_us"]),0)
    def test_nested_isr_inclusive_equals_original(self):
        a=run(R1,"nested_isr.csv");b=run(R2,"nested_isr.csv")
        self.assertEqual(a.returncode,0)
        self.assertEqual(b.returncode,0)
        self.assertIn("ISR_DURATION,ISR,1,200,200,600",a.stdout)
        self.assertIn("ISR_DURATION,ISR,2,150,50,100",a.stdout)
        self.assertIn("M2_ISR_SUMMARY,id=1,calls=1,inclusive_us=200,exclusive_us=150",b.stdout)
        self.assertIn("M2_ISR_SUMMARY,id=2,calls=1,inclusive_us=50,exclusive_us=50",b.stdout)
    def test_r1_and_r2_both_acknowledge_gap(self):
        a=run(R1,"gap.csv");b=run(R2,"gap.csv")
        self.assertNotEqual(a.returncode,0)
        self.assertEqual(b.returncode,1)  # COMPLETE after missing release -> invalid state
        self.assertIn("TRACE_GAP",a.stdout)
        self.assertIn("M2_GAP,",b.stdout)
        self.assertIn("unknown_us=",b.stdout)
if __name__=="__main__": unittest.main()
