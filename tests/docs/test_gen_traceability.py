import pytest
import os
from scripts.gen_traceability import load_requirements, load_mappings

def test_unknown_test_name_fails(tmp_path):
    map_file = tmp_path / "traceability_map.csv"
    map_file.write_text("requirement_id;test_node_id;level\nR-001;non_existent_test_xyz::test_foo;unit\n")
    
    mappings = load_mappings(str(map_file))
    collected_tests = {"real_test_abc::test_bar"}
    
    invalid = [m for m in mappings if m["test_node_id"] not in collected_tests]
    assert len(invalid) == 1
    assert invalid[0]["requirement_id"] == "R-001"
    assert invalid[0]["test_node_id"] == "non_existent_test_xyz::test_foo"

def test_gap_reported(tmp_path):
    req_file = tmp_path / "REQUIREMENTS.md"
    req_file.write_text("| ID | Requirement Text | Source |\n| **R-001** | First req | src.py |\n| **R-002** | Second req | src.py |\n")
    
    map_file = tmp_path / "traceability_map.csv"
    map_file.write_text("requirement_id;test_node_id;level\nR-001;test_file.py::test_one;unit\n")
    
    reqs = load_requirements(str(req_file))
    mappings = load_mappings(str(map_file))
    
    mapped_rids = {m["requirement_id"] for m in mappings}
    gaps = [rid for rid in reqs if rid not in mapped_rids]
    
    assert "R-002" in gaps
    assert "R-001" not in gaps
