from kiwi_client.public_directory import parse_public_directory


HTML = """
<html><body>
<div class='cl-entry seq_1 snr_all_40 snr_hf_38'>
 <a href='http://example.test:8073' target='_blank'>receiver</a>
 <div class='cl-info'>
  <!-- updated=Monday, 07-Sep-2026 16:20:26 GMT -->
  <!-- id=abc123 -->
  <!-- status=active -->
  <!-- name=Test &amp; SDR | Example site -->
  <!-- sdr_hw=KiwiSDR 2 v1.902 -->
  <!-- bands=0-30000000 -->
  <!-- mode=rx8.wf3 -->
  <!-- users=2 -->
  <!-- users_max=8 -->
  <!-- ext_api=4 -->
  <!-- gps=(44.100000, -85.500000) -->
  <!-- grid=EN74gc -->
  <!-- loc=Example, Michigan -->
  <!-- antenna=Loop &amp; wire -->
  <!-- snr=40,38 -->
  <!-- uptime=12345 -->
 </div>
</div>
<div class='cl-entry seq_2 snr_all_12 snr_hf_9'>
 <a href='http://other.test' target='_blank'>receiver</a>
 <div class='cl-info'>
  <!-- id=def456 -->
  <!-- name=Other SDR -->
  <!-- loc=Unknown -->
  <!-- snr=12,9 -->
  <!-- users=0 -->
  <!-- users_max=4 -->
 </div>
</div>
</body></html>
"""


def test_parse_public_directory_extracts_identity_location_snr_and_metadata():
    receivers = parse_public_directory(HTML)

    assert len(receivers) == 2
    first = receivers[0]
    assert first["url"] == "http://example.test:8073"
    assert first["name"] == "Test & SDR | Example site"
    assert first["location"] == "Example, Michigan"
    assert first["snr_all_db"] == 40
    assert first["snr_hf_db"] == 38
    assert first["users"] == 2
    assert first["users_max"] == 8
    assert first["ext_api"] == 4
    assert first["latitude"] == 44.1
    assert first["longitude"] == -85.5
    assert first["antenna"] == "Loop & wire"
    assert first["metadata"]["bands"] == "0-30000000"
    assert first["metadata"]["uptime"] == "12345"

    assert receivers[1]["url"] == "http://other.test"
    assert receivers[1]["snr_all_db"] == 12
    assert receivers[1]["snr_hf_db"] == 9
    assert receivers[1]["latitude"] is None
