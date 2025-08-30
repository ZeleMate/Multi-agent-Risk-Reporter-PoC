#!/usr/bin/env python3
"""
CI Smoke Test - Basic functionality verification for CI pipeline.
Tests core imports and basic functionality without heavy dependencies.
"""

import sys
import traceback


def test_imports():
    """Test that core modules can be imported."""
    print("Testing core imports...")

    try:
        # Test basic modules
        import importlib.util

        if not importlib.util.find_spec("src.ingestion.parser"):
            raise ImportError("src.ingestion.parser not found")

        if not importlib.util.find_spec("src.ingestion.pii"):
            raise ImportError("src.ingestion.pii not found")

        if not importlib.util.find_spec("src.retrieval.retriever"):
            raise ImportError("src.retrieval.retriever not found")

        if not importlib.util.find_spec("src.retrieval.store"):
            raise ImportError("src.retrieval.store not found")

        if not importlib.util.find_spec("src.services.config"):
            raise ImportError("src.services.config not found")

        print("✓ Core imports successful")
        return True
    except ImportError as e:
        print(f"✗ Import failed: {e}")
        return False


def test_config_loading():
    """Test configuration loading."""
    print("Testing configuration loading...")

    try:
        from src.services.config import get_config

        config = get_config()
        print(f"✓ Config loaded: {config.model.chat_model}")
        return True
    except Exception as e:
        print(f"✗ Config loading failed: {e}")
        traceback.print_exc()
        return False


def test_basic_functionality():
    """Test basic functionality without heavy dependencies."""
    print("Testing basic functionality...")

    try:
        # Test date normalization

        from src.ingestion.parser import normalize_date

        result = normalize_date("Wed, 15 Jan 2024 10:30:00 +0000")
        assert "normalized_date" in result
        print("✓ Date normalization works")

        # Test PII redactor creation

        from src.ingestion.pii import PIIRedactor

        PIIRedactor()  # Test that it can be instantiated
        print("✓ PII redactor creation works")

        return True
    except Exception as e:
        print(f"✗ Basic functionality failed: {e}")
        traceback.print_exc()
        return False


def main():
    """Run all smoke tests."""
    print("=" * 50)
    print("CI Smoke Test Starting...")
    print("=" * 50)

    tests = [
        ("Import Tests", test_imports),
        ("Config Loading", test_config_loading),
        ("Basic Functionality", test_basic_functionality),
    ]

    results = []
    for name, test_func in tests:
        print(f"\n--- {name} ---")
        success = test_func()
        results.append((name, success))

    print("\n" + "=" * 50)
    print("CI Smoke Test Results:")
    print("=" * 50)

    all_passed = True
    for name, success in results:
        status = "PASSED" if success else "FAILED"
        print(f"{name}: {status}")
        if not success:
            all_passed = False

    print("\n" + "=" * 50)
    if all_passed:
        print("All smoke tests PASSED! CI pipeline ready.")
        sys.exit(0)
    else:
        print("Some smoke tests FAILED! Check issues above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
