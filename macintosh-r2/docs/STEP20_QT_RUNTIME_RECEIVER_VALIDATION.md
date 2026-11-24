# CSI4900 Qt 6 runtime receiver validation (Step20)

## Verified: Qt libraries, NOT Xavier's production Qt application

A minimal standalone reference receiver exercises **actual Qt 6.12.0** networking and JSON behavior on Windows. This is not a rewrite, replacement, modification or simulation of Xavier's missing UI source. It validates that Step16's protocol can be accepted by QCoreApplication + Qt QUdpSocket and Qt QJsonDocument before any integration with a shared Qt application.

Files:
- docs/Step20_Qt_Receiver_Reference.py
- tests/test_qt_runtime_receiver.py (14 real Qt tests)
- requirements-qt-runtime.txt (Python Qt bindings pinned)

Qt receives a versioned 1200-byte-maximum compact JSON datagram with schema csi4900.udp.diagnostics.v1, sequence/count, run_id, source R1/R2, explicit provenance, diagnostics SHA-256 and unchanged diagnostic data.

It rejects:
- malformed JSON, unsupported schema/event type, oversized datagrams
- missing, duplicated, reordered or out-of-range sequence numbers
- mixing run IDs/provenance/source hashes in a stream
- incomplete streams (including missing tail datagrams)

It preserves PARTIAL quality flags and unknown microseconds without converting unknown time to idle time.

## Reproducible isolated Windows environment

From the Git worktree root:

    py -3.13 -m venv build/qtcore_venv
    build/qtcore_venv/Scripts/python.exe -m pip install --disable-pip-version-check --no-input -r macintosh-r2/requirements-qt-runtime.txt

The virtual environment is under gitignored build/ and is not committed to GitHub. It does not replace any system-wide Python or Qt installation.

From macintosh-r2:

    ../build/qtcore_venv/Scripts/python.exe -m unittest tests.test_qt_runtime_receiver tests.test_qt_udp_bridge_v1 tests.test_qt_export_v2 tests.test_metrics_v2 tests.test_timer_reference_v2 tests.test_r1_r2_consistency -q

Expected **51/51 tests PASS**, including 14 Qt runtime tests and the earlier 37 host tests. The Qt test class automatically SKIPS (does not fail) when a developer has not installed the optional Qt runtime. Installing PySide6 Essentials is required for a meaningful actual Qt PASS.

## Real local UDP end-to-end smoke test

First run the existing synthetic R2 analyzer and Step10 diagnostics exporter to make validated diagnostics.jsonl, and use Step16 to export packet JSONL. Then:

    ../build/qtcore_venv/Scripts/python.exe docs/Step20_Qt_Receiver_Reference.py --input build/step16_synthetic_demo/qt_udp_packets.jsonl --mode udp-loopback

This creates an actual Windows Qt QUdpSocket bound to 127.0.0.1 and sends seven packets via a separate Python UDP socket; Qt receives and decodes each using QJsonDocument. A second mode uses Qt QJsonDocument to parse the packet stream from the file without network.

Verified 2026-11-24:
- 14/14 newly added Qt tests PASS.
- 51/51 R2/Qt host tests PASS.
- Seven packets sent and received over actual Qt QUdpSocket localhost transport, with original schema, counts and SHA-256 preserved. The observed run ID is collector_qa_synthetic; provenance is synthetic, and displayed quality COMPLETE as in the source.

This does not establish live STM32 firmware, QNX UART receive, external UDP traffic, actual Qt GUI rendering, task visualization, a production receiver, R2 release/completion event semantics, or the 30-minute stability requirement. Xavier must provide the current Qt app for direct integration.

Security: loopback-only diagnostic receiver, not intended for network-facing or authenticated streaming.
