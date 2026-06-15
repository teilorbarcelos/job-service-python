import sys
import subprocess
import re

def run_tests():
    print("Running tests with coverage...")
    result = subprocess.run(
        ["./venv/bin/pytest", "--cov=src", "--cov-fail-under=100"],
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        print(result.stdout)
        print("❌ Tests failed or coverage is below 100%!")
        sys.exit(1)
    
    print("✅ Tests and coverage passed!")

if __name__ == "__main__":
    run_tests()
