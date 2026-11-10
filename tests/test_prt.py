from resdash.prt import extract_prt

FIXTURE = """
 ECHO OF THE SCHEDULE SECTION
 NEW TIME STEP              1 SIZE =   30.0 DAYS
 MATERIAL BALANCE ERROR  AT 2025-02-01:     0.2100E-03 PERCENT
 NEW TIME STEP              2 SIZE =   28.0 DAYS
 MATERIAL BALANCE ERROR  AT 2025-03-01:     0.5400E-02 PERCENT
 NEW TIME STEP              3 SIZE =   31.0 DAYS
 MATERIAL BALANCE ERROR  AT 2025-04-01:     0.1200E-03 PERCENT
 ==========================================
                          :FIELD TOTAL:
   CURRENTLY IN PLACE     :  OIL  SM3      12345670.   GAS  SM3        5432101.
                          :  WATER SM3     76543210.
 FLUID VOLUMES IN PLACE  (SURFACE)  FOR REGION     1
   OIL   SM3      4000000.   GAS  SM3       1000000.   WATER SM3      20000000.
 FLUID VOLUMES IN PLACE  (SURFACE)  FOR REGION     2
   OIL   SM3       8345670.   GAS  SM3       4432101.   WATER SM3      56543210.
 ==========================================
 TOTAL CPU TIME :   0.4321E+05 SECONDS
"""


def test_prt_metrics(tmp_path):
    p = tmp_path / "CASE.PRT"
    p.write_text(FIXTURE, encoding="utf-8")
    qc = extract_prt(str(p))
    assert qc["mb_error_max"] == 0.0054          # 0.54e-2
    assert qc["mb_error_last"] == 0.00012        # 0.12e-3
    assert qc["timesteps"] == 3
    assert abs(qc["cpu_hours"] - 12.0) < 0.01    # 43210 s / 3600
    assert qc["fip_regions"]["1"]["oil_sm3"] == 4_000_000.0
    assert qc["fip_regions"]["2"]["gas_sm3"] == 4_432_101.0


def test_prt_missing_and_unparsable(tmp_path):
    assert extract_prt(None) == {"mb_error_max": None, "mb_error_last": None,
                                 "timesteps": None, "cpu_hours": None, "fip_regions": {}}
    junk = tmp_path / "J.PRT"
    junk.write_text("no keywords here\n", encoding="utf-8")
    qc = extract_prt(str(junk))
    assert qc["mb_error_max"] is None and qc["fip_regions"] == {}
