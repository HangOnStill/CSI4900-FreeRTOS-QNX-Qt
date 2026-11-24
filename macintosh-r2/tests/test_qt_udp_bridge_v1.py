"""Qt-neutral UDP bridge contract tests. No Raspberry Pi or external network."""
import json
from pathlib import Path
import socket
import tempfile
import threading
import unittest
import sys

HERE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE/"docs"))
import Step16_Qt_Neutral_UDP_Bridge as bridge

def record(kind="session",run_id="sample1",provenance="synthetic",source="r2",data=None):
    return {
      "schema":"csi4900.diagnostics.v1", "run_id":run_id,
      "provenance":provenance,"source":source,
      "kind":kind,"data":data or {"elapsed_us":100}
    }
def write_records(path,items):
    Path(path).write_text("".join(json.dumps(x)+"\n" for x in items),encoding="utf-8")

class QtUdpBridgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.path=self.root/"diagnostics.jsonl"
        self.items=[
            record("utilization_window",data={"start_us":0,"end_us":100,
               "elapsed_us":100,"task_us":60,"idle_us":40,"isr_us":0,
               "unknown_us":0,"quality":"COMPLETE","busy_lower_pct":60.0}),
            record("session")
        ]
        write_records(self.path,self.items)

    def test_two_records(self):
        packets=bridge.prepare(self.path)
        summary=bridge.inspect_packets(packets)
        self.assertEqual(summary["records"],2)
        self.assertEqual(summary["run_id"],"sample1")
        self.assertEqual([json.loads(x)["sequence"] for x in packets],[0,1])
        self.assertTrue(all(len(x)<=1200 for x in packets))

    def test_qa_quality_not_replaced(self):
        self.items[0]["data"]["quality"]="PARTIAL"
        self.items[0]["data"]["unknown_us"]=50
        write_records(self.path,self.items)
        p=bridge.prepare(self.path)
        rec=json.loads(p[0])
        self.assertEqual(rec["data"]["unknown_us"],50)
        self.assertEqual(rec["data"]["quality"],"PARTIAL")

    def test_bad_schema(self):
        self.items[0]["schema"]="example.bad"
        write_records(self.path,self.items)
        with self.assertRaisesRegex(ValueError,"schema"):
            bridge.prepare(self.path)

    def test_mixed_run(self):
        self.items[1]["run_id"]="different"
        write_records(self.path,self.items)
        with self.assertRaisesRegex(ValueError,"mix"):
            bridge.prepare(self.path)

    def test_source_provenance_mismatch(self):
        self.items[1]["provenance"]="captured"
        write_records(self.path,self.items)
        with self.assertRaisesRegex(ValueError,"mix"):
            bridge.prepare(self.path)

    def test_oversized_record_rejected(self):
        self.items[1]["data"]["oversize"]="A"*1800
        write_records(self.path,self.items)
        with self.assertRaisesRegex(ValueError,"exceeds"):
            bridge.prepare(self.path)

    def test_corrupted_sequence_detected(self):
        packets=bridge.prepare(self.path)
        with self.assertRaisesRegex(ValueError,"sequence"):
            bridge.inspect_packets(packets[::-1])

    def test_file_export_and_no_overwrite(self):
        packets=bridge.prepare(self.path)
        outfile=self.root/"events.udp.jsonl"
        bridge.emit_to_file(packets,outfile)
        self.assertEqual(outfile.read_bytes().splitlines(),packets)
        with self.assertRaises(FileExistsError):
            bridge.emit_to_file(packets,outfile)

    def test_nonloopback_requires_explicit_optin(self):
        packets=bridge.prepare(self.path)
        with self.assertRaisesRegex(ValueError,"Nonloopback"):
            bridge.emit_udp(packets,"192.0.2.5",49000)

    def test_hostname_refused(self):
        with self.assertRaisesRegex(ValueError,"literal"):
            bridge.emit_udp(bridge.prepare(self.path),"example.com",49000)

    def test_exact_udp_loopback_datagrams(self):
        packets=bridge.prepare(self.path)
        observed=[]
        ready=threading.Event()
        def receiver(sock):
            ready.set()
            for _ in packets:
                data,_=sock.recvfrom(2048)
                observed.append(data)
        with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as server:
            server.bind(("127.0.0.1",0))
            server.settimeout(3)
            port=server.getsockname()[1]
            thread=threading.Thread(target=receiver,args=(server,),daemon=True)
            thread.start()
            self.assertTrue(ready.wait(1))
            bridge.emit_udp(packets,"127.0.0.1",port)
            thread.join(timeout=4)
            self.assertFalse(thread.is_alive(),"UDP loopback receiver stalled")
        self.assertEqual(observed,packets)

    def test_real_step10_export_record_compatibility(self):
        # Exercise source exporter behavior directly (not simulated or forged Qt UI).
        import Step10_Export_Qt_Diagnostics as src
        analysis=self.root/"r2_analysis.txt"
        analysis.write_text(
          "M2_WINDOW,start_us=0,end_us=100,elapsed_us=100,task_us=60,isr_us=0,idle_us=40,"
          "unknown_us=0,busy_lower_pct=60,quality=COMPLETE\n"
          "M2_SESSION,elapsed_us=100,task_us=60,isr_us=0,idle_us=40,unknown_us=0\n",
          encoding="utf-8")
        out=self.root/"step10"
        src.export(analysis,None,out,"independent_qa","synthetic")
        self.assertEqual(bridge.inspect_packets(bridge.prepare(out/"diagnostics.jsonl"))["records"],2)

if __name__=="__main__":
    unittest.main()
