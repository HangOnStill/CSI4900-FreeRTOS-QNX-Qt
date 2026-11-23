"""Qt-neutral R2 exporter regression tests, synthetic fixtures only."""
import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"docs"))
import Step10_Export_Qt_Diagnostics as exporter
R2_EXE=ROOT/"build"/"trace_metrics_v2_host.exe"
R1_EXE=ROOT/"build"/"trace_analyzer_host.exe"
def execute(exe,fixture):
    config="r2_idle_config.csv" if fixture=="r2_idle.csv" else "config.csv"
    return subprocess.run([str(exe),str(ROOT/"fixtures"/config),
                str(ROOT/"fixtures"/fixture), "100"] if exe==R2_EXE else
                [str(exe),str(ROOT/"fixtures"/"config.csv"),
                 str(ROOT/"fixtures"/fixture)],capture_output=True,text=True,timeout=8)

class QtExportTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name)
        r2=execute(R2_EXE,"normal.csv")
        r1=execute(R1_EXE,"normal.csv")
        self.assertEqual(r2.returncode,0,r2.stderr)
        self.assertEqual(r1.returncode,0,r1.stderr)
        self.r2=self.base/"r2.txt";self.r1=self.base/"r1.txt"
        self.r2.write_text(r2.stdout,encoding="utf-8")
        self.r1.write_text(r1.stdout,encoding="utf-8")
        self.dest=self.base/"results"

    def test_end_to_end_json_csv(self):
        results=exporter.export(self.r2,self.r1,self.dest,"test_synthetic","synthetic",ROOT/"fixtures"/"normal.csv")
        self.assertEqual(results["windows"],130)
        self.assertGreater(results["records"],18)
        with (self.dest/"diagnostics.jsonl").open(encoding="utf-8") as f:
            docs=[json.loads(line) for line in f]
        self.assertTrue(all(x["schema"]=="csi4900.diagnostics.v1" for x in docs))
        self.assertTrue(all(x["provenance"]=="synthetic" for x in docs))
        self.assertTrue(any(x["kind"]=="isr_window" for x in docs))
        with (self.dest/"utilization_windows.csv").open(newline="",encoding="utf-8") as f:
            rows=list(csv.DictReader(f))
        self.assertEqual(len(rows),130)
        self.assertEqual(sum(int(x["unknown_us"]) for x in rows),6800)
        with (self.dest/"warnings.csv").open(newline="",encoding="utf-8") as f:
            warnings=list(csv.DictReader(f))
        self.assertTrue(any(x["code"]=="DEADLINE_MISS" for x in warnings))
        manifest=json.loads((self.dest/"manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["windows"],130)

    def test_reject_window_mismatch(self):
        text=self.r2.read_text(encoding="utf-8")
        self.r2.write_text(text.replace("task_us=100,isr_us=0","task_us=101,isr_us=0",1),
                           encoding="utf-8")
        with self.assertRaisesRegex(ValueError,"Exclusive CPU accounting invalid"):
            exporter.export(self.r2,None,self.dest,"synthetic_bad","synthetic")

    def test_reject_wrong_session_total(self):
        text=self.r2.read_text(encoding="utf-8")
        self.r2.write_text(text.replace("M2_SESSION,elapsed_us=13000",
                                        "M2_SESSION,elapsed_us=13001"),encoding="utf-8")
        with self.assertRaisesRegex(ValueError,"windows do not cover"):
            exporter.export(self.r2,None,self.dest,"synthetic_bad","synthetic")

    def test_reject_invalid_run_id(self):
        with self.assertRaises(ValueError):
            exporter.export(self.r2,None,self.dest,"../bad","synthetic")

    def test_repeat_export_byte_determinism(self):
        exporter.export(self.r2,self.r1,self.dest,"repeat","synthetic",ROOT/"fixtures"/"normal.csv")
        one=(self.dest/"diagnostics.jsonl").read_bytes()
        exporter.export(self.r2,self.r1,self.dest,"repeat","synthetic",ROOT/"fixtures"/"normal.csv")
        self.assertEqual(one,(self.dest/"diagnostics.jsonl").read_bytes())

    def test_r2_without_r1_analyzer(self):
        exporter.export(self.r2,None,self.dest,"r2_only","synthetic")
        with (self.dest/"diagnostics.jsonl").open(encoding="utf-8") as f:
            docs=[json.loads(x) for x in f]
        self.assertTrue(all(x["source"]=="r2" for x in docs))
if __name__=="__main__":unittest.main()
