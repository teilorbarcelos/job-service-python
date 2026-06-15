import pytest
import sys

if __name__ == "__main__":
    retcode = pytest.main(["--cov=src", "--cov-report=term-missing", "tests/test_audit_failure_coverage.py", "tests/modules/audit/test_audit.py"])
    sys.exit(retcode)
