"""Bounded raw capture regression; does not require actual UART device."""
from pathlib import Path
import binascii
import os
import struct
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
EXE=ROOT/"build"/"uart_capture_v1_host.exe"
DECODER=ROOT/"build"/"uart_collector_v1_host.exe"

def source_frame(sequence=0):
    def hash_task(name):
        out=2166136261
        for v in name.encode("ascii"):
            out=((out^v)*16777619)&0xffffffff
        return out
    events=(struct.pack("<BIII",1,hash_task("SensorTask"),160,0)
           +struct.pack("<BIII",2,hash_task("SensorTask"),320,0))
    raw=b"\xa5\x5a"+bytes([1])+struct.pack("<H",10+len(events))
    raw+=struct.pack("<I",sequence)+bytes([2])+events
    raw+=struct.pack("<H",binascii.crc_hqx(raw[2:],0xffff))
    return raw

class BoundedRawCapture(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.fixture=self.root/"source.bin"
        self.output=self.root/"capture.bin"

    def invoke(self, *args):
        return subprocess.run([str(EXE),*args],capture_output=True,text=True,
                              timeout=8)

    def test_binary_exists(self):
        self.assertTrue(EXE.is_file())

    def test_preserves_exact_v1_bytes(self):
        data=source_frame(0)+source_frame(1)
        self.fixture.write_bytes(data)
        p=self.invoke("--fixture",str(self.fixture),"--raw-output",str(self.output))
        self.assertEqual(p.returncode,0,p.stderr)
        self.assertEqual(self.output.read_bytes(),data)
        self.assertIn("raw_bytes="+str(len(data)),p.stderr)

    def test_raw_capture_decodes_identically(self):
        self.assertTrue(DECODER.exists())
        data=source_frame()
        self.fixture.write_bytes(data)
        p=self.invoke("--fixture",str(self.fixture),"--raw-output",str(self.output))
        self.assertEqual(p.returncode,0,p.stderr)
        decoded=subprocess.run([str(DECODER),"--fixture",str(self.output),
                                "--cycles-per-us","16"],capture_output=True,
                                text=True,timeout=8)
        self.assertEqual(decoded.returncode,0,decoded.stderr)
        self.assertEqual(decoded.stdout.splitlines(),
                         ["0,SWITCH_IN,1","10,SWITCH_OUT,1"])

    def test_existing_output_cannot_be_overwritten(self):
        self.fixture.write_bytes(source_frame())
        self.output.write_bytes(b"PROTECTED")
        p=self.invoke("--fixture",str(self.fixture),"--raw-output",str(self.output))
        self.assertNotEqual(p.returncode,0)
        self.assertEqual(self.output.read_bytes(),b"PROTECTED")

    def test_same_path_rejected_before_read(self):
        self.fixture.write_bytes(source_frame())
        p=self.invoke("--fixture",str(self.fixture),"--raw-output",str(self.fixture))
        self.assertEqual(p.returncode,2)
        self.assertEqual(self.fixture.read_bytes(),source_frame())

    def test_byte_bound_is_enforced(self):
        data=source_frame()+source_frame()
        self.fixture.write_bytes(data)
        p=self.invoke("--fixture",str(self.fixture),"--raw-output",str(self.output),
                      "--max-bytes","10")
        self.assertEqual(p.returncode,0,p.stderr)
        self.assertEqual(self.output.read_bytes(),data[:10])
        self.assertIn("limit_reached=1",p.stderr)

    def test_empty_source_is_no_data_not_pass(self):
        self.fixture.write_bytes(b"")
        p=self.invoke("--fixture",str(self.fixture),"--raw-output",str(self.output))
        self.assertEqual(p.returncode,3)
        self.assertEqual(self.output.read_bytes(),b"")

    def test_zero_duration_refused(self):
        p=self.invoke("--fixture",str(self.fixture),"--raw-output",str(self.output),
                      "--seconds","0")
        self.assertEqual(p.returncode,2)

    def test_negative_max_bytes_refused(self):
        p=self.invoke("--fixture",str(self.fixture),"--raw-output",str(self.output),
                      "--max-bytes","-1")
        self.assertEqual(p.returncode,2)

    def test_duplicate_input_options_refused(self):
        p=self.invoke("--fixture",str(self.fixture),"--device","/dev/ser2",
                      "--raw-output",str(self.output))
        self.assertEqual(p.returncode,2)

    def test_missing_raw_output_refused(self):
        p=self.invoke("--fixture",str(self.fixture))
        self.assertEqual(p.returncode,2)

    def test_device_not_supported_on_windows(self):
        if os.name=="nt":
            p=self.invoke("--device","/dev/ser2","--raw-output",str(self.output))
            self.assertEqual(p.returncode,2)

if __name__=="__main__":unittest.main()
