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
import re
import signal
import sys
from pathlib import Path
from argparse import ArgumentParser, Namespace
from typing import Optional, List, Dict, Any

log = logging.getLogger('collectjson')


def detect_root_schema():
    """Detect FITS root directory schema (OCM, CAMK, or Mik)."""
    root_propositions = {
        'OCM': Path('/data/fits'),
        'CAMK': Path('/work/vela/oca/fits'),
        'Mik': Path('/Users/Shared/oca_data/fits')
    }

    for schema, path in root_propositions.items():
        if path.is_dir():
            return schema, path

    return None, None


def extract_metadata(name: str) -> Optional[Dict[str, str]]:
    """Extract metadata from OCA FITS filename.

    Examples:
        zb08c_0571_24540.fits -> {telescope: zb08, instr: c, night: 0571, count: 24540}
        zb08c_0571_24540_zdf.fits -> same + {suffix: zdf}
        zb08c_0571_24540_master_z.fits -> same + {suffix: master_z}
    """
    m = re.match(r'(?P<telescope>\w{4})(?P<instr>.)_(?P<night>\d{4})_(?P<count>\d{5})(?:_(?P<suffix>.*))?\.fits', name)
    if m:
        return m.groupdict()
    return None


def reconstruct_path(name: str, root_path: Path) -> str:
    """Reconstruct full path from filename based on naming convention.

    Examples:
        zb08c_0571_24540.fits -> /root/zb08/raw/0571/zb08c_0571_24540.fits
        zb08c_0571_24540_zdf.fits -> /root/zb08/processed-ofp/science/0571/zb08c_0571_24540/zb08c_0571_24540_zdf.fits
        zb08c_0571_24540_master_z.fits -> /root/zb08/processed-ofp/zeros/zb08c_0571_24540/zb08c_0571_24540_master_z.fits
    """
    metadata = extract_metadata(name)
    if not metadata:
        return name

    telescope = metadata['telescope']
    night = metadata['night']
    suffix = metadata.get('suffix', '')
    basename = f"{metadata['telescope']}{metadata['instr']}_{metadata['night']}_{metadata['count']}"

    if not suffix:
        # Raw file
        return str(root_path / telescope / 'raw' / night / name)
    elif suffix == 'zdf':
        # ZDF processed file
        return str(root_path / telescope / 'processed-ofp' / 'science' / night / basename / name)
    elif suffix.startswith('master_z'):
        # Master zero
        return str(root_path / telescope / 'processed-ofp' / 'zeros' / basename / name)
    elif suffix.startswith('master_d'):
        # Master dark
        return str(root_path / telescope / 'processed-ofp' / 'darks' / basename / name)
    elif suffix.startswith('master_f'):
        # Master flat (has filter in suffix)
        return str(root_path / telescope / 'processed-ofp' / 'flats' / name)
    else:
        # Unknown, return in science dir
        return str(root_path / telescope / 'processed-ofp' / 'science' / night / basename / name)


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

        # Count leading spaces
        indent = len(line) - len(line.lstrip(' '))
        file_path = line.strip()

        # Reconstruct full path if needed
        if root_path and not file_path.startswith('/'):
            full_path = reconstruct_path(Path(file_path).name, root_path)
        else:
            full_path = file_path

        name = Path(file_path).name

        if indent == 0:
            # New observation
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
    schema, root_path = detect_root_schema()
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

