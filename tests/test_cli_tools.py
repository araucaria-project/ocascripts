#!/usr/bin/env python3
"""Simple tests for new CLI tools."""

import sys
import subprocess
from pathlib import Path
from io import StringIO

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

def test_fitscollect_help():
    """Test fitscollect --help works."""
    result = subprocess.run(
        ['python3', '-m', 'ocascripts.fitscollect', '--help'],
        capture_output=True,
        text=True
    )
    assert result.returncode == 0
    assert 'fitscollect' in result.stdout.lower() or 'usage' in result.stdout.lower()
    print("✓ fitscollect --help works")


def test_fitscollectjson_simple():
    """Test fitscollectjson with simple input."""
    from ocascripts.fitscollectjson import extract_metadata, reconstruct_path

    # Test metadata extraction
    meta = extract_metadata('zb08c_0571_24540.fits')
    assert meta is not None
    assert meta['telescope'] == 'zb08'
    assert meta['night'] == '0571'
    assert meta['count'] == '24540'
    print("✓ Metadata extraction works")

    # Test path reconstruction
    root = Path('/work/vela/oca/fits')
    path = reconstruct_path('zb08c_0571_24540.fits', root)
    assert 'zb08/raw/0571' in path
    print("✓ Path reconstruction works")

    path_zdf = reconstruct_path('zb08c_0571_24540_zdf.fits', root)
    assert 'processed-ofp/science' in path_zdf
    print("✓ ZDF path reconstruction works")


def test_fitscollectcalib_help():
    """Test fitscollectcalib --help works."""
    result = subprocess.run(
        ['python3', '-m', 'ocascripts.fitscollectcalib', '--help'],
        capture_output=True,
        text=True
    )
    assert result.returncode == 0
    assert 'calibration' in result.stdout.lower()
    print("✓ fitscollectcalib --help works")


def test_fitscollectcalib_extract():
    """Test fitscollectcalib basename extraction."""
    from ocascripts.fitscollectcalib import extract_basename

    assert extract_basename('zb08c_0571_24540.fits') == 'zb08c_0571_24540'
    assert extract_basename('zb08c_0571_24540_zdf.fits') == 'zb08c_0571_24540'
    assert extract_basename('/path/to/zb08c_0571_24540.fits') == 'zb08c_0571_24540'
    print("✓ Basename extraction works")


if __name__ == '__main__':
    print("Running simple tests...")

    try:
        test_fitscollect_help()
        test_fitscollectjson_simple()
        test_fitscollectcalib_help()
        test_fitscollectcalib_extract()

        print("\n✅ All tests passed!")
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)

