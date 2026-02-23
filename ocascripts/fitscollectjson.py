"""Converts a list of FITS files to JSON format.

Takes a list of FITS files (from stdin or positional arguments) and outputs structured JSON.
Understands indentation from fitscollectcalib to create nested observation structures.

If input contains only filenames (no paths), reconstructs full paths based on detected
root directory schema and file naming convention.

v. 1.0.0
"""
import argparse
import json
import logging
import signal
import sys
from pathlib import Path
from argparse import ArgumentParser, Namespace
from typing import Optional, List, Dict, Any

from ocafitsfiles import detect_fits_root, parse_metadata, canonical_path

log = logging.getLogger('collectjson')



def _reconstruct_path(name: str, root_path: Path) -> str:
    """Reconstruct full path from filename using ocafitsfiles.canonical_path."""
    meta = parse_metadata(name)
    if not meta:
        return name
    basename = f"{meta['telescope']}{meta['instr']}_{meta['night']}_{meta['count']}"
    suffix = meta.get('suffix') or None
    p = canonical_path(basename, suffix, root_path)
    return str(p) if p else name


def parse_indented_list(lines: List[str], root_path: Optional[Path]) -> List[Dict[str, Any]]:
    """Parse indented file list into structured observations.

    Indentation (spaces at line start) indicates dependency structure.
    Level 0: Science observations
    Level 1+: Calibration files
    """
    observations = []
    current_obs = None
    indent_stack = []

    for line in lines:
        line = line.rstrip('\n')
        if not line.strip():
            continue

        indent = len(line) - len(line.lstrip(' '))
        file_path = line.strip()

        if root_path and not file_path.startswith('/'):
            full_path = _reconstruct_path(Path(file_path).name, root_path)
        else:
            full_path = file_path

        name = Path(file_path).name

        if indent == 0:
            current_obs = {
                'observation': Path(name).stem,
                'name': name,
                'path': full_path,
                'files': []
            }
            observations.append(current_obs)
            indent_stack = [current_obs['files']]
        elif current_obs and indent > 0:
            # Calibration file - add to appropriate level
            file_entry = {
                'name': name,
                'path': full_path
            }

            # Add to parent at indent-1 level
            if indent <= len(indent_stack):
                indent_stack[indent - 1].append(file_entry)

    return observations


def process_files(file_list: List[str], args: Namespace):
    """Process list of files and output as JSON."""
    schema, root_path = detect_fits_root()
    if not schema and not args.dir:
        log.warning('Cannot detect FITS root directory, paths will not be reconstructed')
        root_path = None
    elif args.dir:
        root_path = Path(args.dir)

    log.debug(f'Using schema: {schema}, root: {root_path}')

    observations = parse_indented_list(file_list, root_path)

    # Output JSON
    print(json.dumps(observations, indent=2))


def main() -> int:
    argparser = ArgumentParser(description=__doc__,
                               formatter_class=argparse.RawDescriptionHelpFormatter)

    # Input
    argparser.add_argument('files', nargs='*', help='FITS files (reads from stdin if not provided)')

    # General
    general_group = argparser.add_argument_group('general options')
    general_group.add_argument('-D', '--dir', help='Root FITS dir (default: autodetect)')
    general_group.add_argument('-v', '--verbose', help='Increase verbosity', action='count', default=0)

    argparser.epilog = """
examples:

    Simple conversion:
        fitscollect -o ngc300 -f V | fitscollectjson
        
    With calibration files:
        fitscollect -o ngc300 -f V | fitscollectcalib --master-calib | fitscollectjson
        
    From file list:
        fitscollectjson file1.fits file2.fits file3.fits
        
    Reconstruct paths with specific root:
        echo "zb08c_0571_24540_zdf.fits" | fitscollectjson -D /work/vela/oca/fits
    """

    args = argparser.parse_args()

    # SIGPIPE handling
    try:
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    except (AttributeError, ValueError):
        pass

    # Logging
    log_format = '%(asctime)s [%(levelname)s] [%(name)s] %(message)s'
    if args.verbose == 1:
        logging.basicConfig(level=logging.INFO, format=log_format)
    elif args.verbose > 1:
        logging.basicConfig(level=logging.DEBUG, format=log_format)
    else:
        logging.basicConfig(level=logging.WARNING, format=log_format)

    # Get file list from stdin or args
    if args.files:
        file_list = args.files
    else:
        file_list = sys.stdin.readlines()

    process_files(file_list, args)

    return 0


if __name__ == "__main__":
    try:
        ret_code = main()
        exit(ret_code)
    except BrokenPipeError:
        try:
            sys.stdout.close()
        finally:
            exit(0)

