#!/usr/bin/env python3
"""Test output processors."""

import sys
from io import StringIO
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from ocascripts.output_processor import (
    LineOutputProcessor,
    JsonOutputProcessor,
    create_output_processor
)
import json


def test_line_output_paths():
    """Test line output with full paths."""
    stream = StringIO()
    processor = LineOutputProcessor(output_names=False, stream=stream)

    processor.begin_observation('test_obs')
    processor.add_file({'path': '/path/to/file1.fits', 'class': 'zdf'})
    processor.add_file({'path': '/path/to/file2.fits', 'class': 'raw'})
    processor.end_observation()
    processor.finalize()

    output = stream.getvalue()
    lines = output.strip().split('\n')

    assert len(lines) == 2
    assert lines[0] == '/path/to/file1.fits'
    assert lines[1] == '/path/to/file2.fits'
    print("✓ test_line_output_paths passed")


def test_line_output_names():
    """Test line output with names only."""
    stream = StringIO()
    processor = LineOutputProcessor(output_names=True, stream=stream)

    processor.begin_observation('test_obs')
    processor.add_file({'path': '/path/to/file1.fits', 'class': 'zdf'})
    processor.add_file({'path': Path('/path/to/file2.fits'), 'class': 'raw'})
    processor.end_observation()
    processor.finalize()

    output = stream.getvalue()
    lines = output.strip().split('\n')

    assert len(lines) == 2
    assert lines[0] == 'file1.fits'
    assert lines[1] == 'file2.fits'
    print("✓ test_line_output_names passed")


def test_json_output():
    """Test JSON output."""
    stream = StringIO()
    processor = JsonOutputProcessor(indent=2, stream=stream)

    processor.begin_observation('test_obs_1', metadata={'night': '1075', 'telescope': 'zb08'})
    processor.add_file({'path': '/path/file1.fits', 'class': 'zdf'})
    processor.add_file({'path': '/path/file2.fits', 'class': 'raw'})
    processor.end_observation()

    processor.begin_observation('test_obs_2')
    processor.add_file({'path': '/path/file3.fits', 'class': 'master_zero'})
    processor.end_observation()

    processor.finalize()

    output = stream.getvalue()
    data = json.loads(output)

    assert len(data) == 2
    assert data[0]['observation'] == 'test_obs_1'
    assert data[0]['night'] == '1075'
    assert data[0]['telescope'] == 'zb08'
    assert len(data[0]['files']) == 2
    assert data[0]['files'][0]['class'] == 'zdf'
    assert data[0]['files'][1]['class'] == 'raw'

    assert data[1]['observation'] == 'test_obs_2'
    assert len(data[1]['files']) == 1
    assert data[1]['files'][0]['class'] == 'master_zero'

    print("✓ test_json_output passed")


def test_json_output_with_metadata():
    """Test JSON output with file metadata."""
    stream = StringIO()
    processor = JsonOutputProcessor(indent=2, stream=stream)

    processor.begin_observation('test_obs')
    processor.add_file({
        'path': '/path/master_flat.fits',
        'class': 'master_flat',
        'filter': 'V',
        'sources': ['raw1', 'raw2', 'raw3']
    })
    processor.end_observation()
    processor.finalize()

    output = stream.getvalue()
    data = json.loads(output)

    assert len(data) == 1
    file_info = data[0]['files'][0]
    assert file_info['class'] == 'master_flat'
    assert file_info['filter'] == 'V'
    assert file_info['sources'] == ['raw1', 'raw2', 'raw3']

    print("✓ test_json_output_with_metadata passed")


def test_factory():
    """Test factory function."""
    proc1 = create_output_processor('line', output_names=True)
    assert isinstance(proc1, LineOutputProcessor)

    proc2 = create_output_processor('json', indent=4)
    assert isinstance(proc2, JsonOutputProcessor)

    print("✓ test_factory passed")


def test_context_manager():
    """Test context manager style."""
    stream = StringIO()
    processor = JsonOutputProcessor(indent=2, stream=stream)

    with processor.observation('test_obs', metadata={'night': '1075'}):
        processor.add_file({'path': '/path/file.fits', 'class': 'zdf'})

    processor.finalize()

    output = stream.getvalue()
    data = json.loads(output)

    assert len(data) == 1
    assert data[0]['observation'] == 'test_obs'
    assert data[0]['night'] == '1075'

    print("✓ test_context_manager passed")


if __name__ == '__main__':
    print("Running output processor tests...")
    test_line_output_paths()
    test_line_output_names()
    test_json_output()
    test_json_output_with_metadata()
    test_factory()
    test_context_manager()
    print("\n✅ All tests passed!")

