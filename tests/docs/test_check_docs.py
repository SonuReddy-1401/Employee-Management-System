import pytest
import os
from scripts.check_docs import check_file, load_fact_ids

@pytest.fixture
def mock_fact_ids(tmp_path):
    facts_file = tmp_path / "FACTS.md"
    facts_file.write_text("| ID |\n| [F-001] |\n| [F-002] |\n")
    return load_fact_ids(str(facts_file))

def test_fact_citation_good_and_bad(tmp_path, mock_fact_ids):
    good_file = tmp_path / "good.md"
    good_file.write_text("This system has containers [F-001].")
    errors_good = check_file(str(good_file), mock_fact_ids)
    assert not any("Fact citation" in e for e in errors_good)

    bad_file = tmp_path / "bad.md"
    bad_file.write_text("This feature has citation [F-999].")
    errors_bad = check_file(str(bad_file), mock_fact_ids)
    assert any("Fact citation [F-999] not found" in e for e in errors_bad)

def test_backtick_repo_path_good_and_bad(tmp_path, mock_fact_ids):
    good_file = tmp_path / "good_path.md"
    good_file.write_text("See `docker-compose.yml` for configuration.")
    errors_good = check_file(str(good_file), mock_fact_ids)
    assert not any("Repo file path in backticks does not exist" in e for e in errors_good)

    bad_file = tmp_path / "bad_path.md"
    bad_file.write_text("Check `non_existent_file_xyz_123.py` for details.")
    errors_bad = check_file(str(bad_file), mock_fact_ids)
    assert any("Repo file path in backticks does not exist: `non_existent_file_xyz_123.py`" in e for e in errors_bad)

def test_code_fence_balance_good_and_bad(tmp_path, mock_fact_ids):
    good_file = tmp_path / "good_fence.md"
    good_file.write_text("```python\nprint('hello')\n```")
    errors_good = check_file(str(good_file), mock_fact_ids)
    assert not any("Unbalanced code fences" in e for e in errors_good)

    bad_file = tmp_path / "bad_fence.md"
    bad_file.write_text("```python\nprint('hello')\n")
    errors_bad = check_file(str(bad_file), mock_fact_ids)
    assert any("Unbalanced code fences" in e for e in errors_bad)

def test_marketing_words_good_and_bad(tmp_path, mock_fact_ids):
    good_file = tmp_path / "good_words.md"
    good_file.write_text("The architecture handles requests using Python and FastAPI.")
    errors_good = check_file(str(good_file), mock_fact_ids)
    assert not any("Banned word or placeholder found" in e for e in errors_good)

    bad_file = tmp_path / "bad_words.md"
    bad_file.write_text("This platform provides a robust and seamless solution.")
    errors_bad = check_file(str(bad_file), mock_fact_ids)
    assert any("Banned word or placeholder found: 'robust'" in e for e in errors_bad)
    assert any("Banned word or placeholder found: 'seamless'" in e for e in errors_bad)

def test_secret_scanning_good_and_bad(tmp_path, mock_fact_ids):
    good_file = tmp_path / "good_secret.md"
    good_file.write_text("Configure using ADMIN_PASSWORD environment variable.")
    errors_good = check_file(str(good_file), mock_fact_ids)
    assert not any("Secret pattern detected" in e for e in errors_good)

    bad_file = tmp_path / "bad_secret.md"
    bad_file.write_text("Connect using password = 'supersecretpassword123'.")
    errors_bad = check_file(str(bad_file), mock_fact_ids)
    assert any("Secret pattern detected" in e for e in errors_bad)
