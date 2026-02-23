"""Adds calibration files to a list of OCM FITS files.

Takes a list of FITS files (from stdin or positional arguments) and outputs the same list
plus all related calibration files (master and/or raw zero, dark, flat).

Files may have full paths or just basenames. Full path is ignored for calibration discovery, but preserved in output.

Output structure uses indentation (1 space per level) to show dependency relationships:
- Original science files at indent level 0
- Calibration files at deeper levels, reflecting their dependency tree:

    ZDF / raw
    ├── master_flat ──► master_dark ──► master_zero ──► raw_zero
    │                │               └── raw_dark
    │                └── raw_flat
    ├── master_dark ──► master_zero ──► raw_zero
    │               └── raw_dark
    └── master_zero ──► raw_zero

When requesting a file type, all intermediate nodes are traversed to collect it,
e.g. --master-zero will also search inside master_flat and master_dark to find
all master zeros used (directly or indirectly) in producing the input file.

v. 1.0.0
"""
import argparse
import logging
import signal
import sys
from pathlib import Path
from argparse import ArgumentParser, Namespace
from typing import Optional, List

from ocafitsfiles import (
    detect_fits_root,
    parse_filename,
    iter_calib_files,
)

log = logging.getLogger('collectcalib')


def process_files(file_list: List[str], args: Namespace):
    """Process list of files and output with calibration files."""
    if args.dir:
        root_path = Path(args.dir)
        if not root_path.is_dir():
            log.error(f'Provided root path is not a directory: {root_path}')
            return
        schema = 'custom'
    else:
        schema, root_path = detect_fits_root()
    if not schema:
        log.error('Cannot detect FITS root directory')
        return

    log.info(f'Using schema: {schema}, root: {root_path}')

    seen = set()
    stats = {'source': 0, 'master_zero': 0, 'master_dark': 0, 'master_flat': 0,
             'raw_zero': 0, 'raw_dark': 0, 'raw_flat': 0, 'duplicates': 0}

    def emit(path_str: str, level: int, kind: str, dedup_basename: str, dedup_suffix: Optional[str]):
        if args.skip_duplicates:
            dedup_key = f'{dedup_basename}_{dedup_suffix}' if dedup_suffix else dedup_basename
            if dedup_key in seen:
                stats['duplicates'] += 1
                return False
            seen.add(dedup_key)
        indent = '' if args.no_indent else (' ' * level)
        out = Path(path_str).name if args.names else path_str
        print(f'{indent}{out}')
        stats[kind] = stats.get(kind, 0) + 1
        return True

    def suffix_to_kind(suffix: Optional[str]) -> str:
        if suffix in ('zdf', None):             return 'source'
        if suffix == 'master_z':                return 'master_zero'
        if suffix == 'master_d':                return 'master_dark'
        if suffix and suffix.startswith('master_f_'): return 'master_flat'
        return 'source'

    calib_kwargs = dict(
        master_zero=args.master_zero, master_dark=args.master_dark, master_flat=args.master_flat,
        raw_zero=args.raw_zero,       raw_dark=args.raw_dark,       raw_flat=args.raw_flat,
    )

    for file_path in file_list:
        file_path = file_path.strip()
        if not file_path:
            continue

        if not args.skip_source:
            _, suf = parse_filename(file_path)
            emit(file_path, 0, suffix_to_kind(suf), file_path, None)
        else:
            stats['source'] += 1

        basename, suffix = parse_filename(file_path)
        if not basename:
            log.warning(f'Cannot extract basename from: {file_path}')
            continue

        for cpath, level, kind, cb, cs in iter_calib_files(basename, suffix, root_path, **calib_kwargs):
            emit(str(cpath), level, kind, cb, cs)

    total_out = sum(v for k, v in stats.items() if k not in ('duplicates', 'source'))
    log.info(
        f'Source files: {stats["source"]} | '
        f'master zero: {stats["master_zero"]}, dark: {stats["master_dark"]}, flat: {stats["master_flat"]} | '
        f'raw zero: {stats["raw_zero"]}, dark: {stats["raw_dark"]}, flat: {stats["raw_flat"]} | '
        f'total calib output: {total_out}'
        + (f' | duplicates skipped: {stats["duplicates"]}' if args.skip_duplicates else '')
    )


def main() -> int:
    argparser = ArgumentParser(description=__doc__,
                               formatter_class=argparse.RawDescriptionHelpFormatter)

    # Input
    argparser.add_argument('files', nargs='*', help='FITS files (reads from stdin if not provided)')

    # Calibration selection
    calib_group = argparser.add_argument_group('calibration selection', 'Select which calibration files to include')
    calib_group.add_argument('-R', '--raw-calib', help='Include raw calibration (implies --raw-zero, --raw-dark, --raw-flat)', action='store_true')
    calib_group.add_argument('--raw-zero', help='Include raw ZERO (bias) images', action='store_true')
    calib_group.add_argument('--raw-dark', help='Include raw DARK images', action='store_true')
    calib_group.add_argument('--raw-flat', help='Include raw FLAT images', action='store_true')
    calib_group.add_argument('-M', '--master-calib', help='Include master calibration (implies --master-zero, --master-dark, --master-flat)', action='store_true')
    calib_group.add_argument('--master-zero', help='Include master ZERO images', action='store_true')
    calib_group.add_argument('--master-dark', help='Include master DARK images', action='store_true')
    calib_group.add_argument('--master-flat', help='Include master FLAT images', action='store_true')

    # Output options
    output_group = argparser.add_argument_group('output options', 'Control output format')
    output_group.add_argument('-s', '--skip-source', help='Do not output original input files', action='store_true')
    output_group.add_argument('-d', '--skip-duplicates', help='Skip duplicate files (same path) in output', action='store_true')
    output_group.add_argument('-n', '--names', help='Print filenames only, not full paths', action='store_true')
    output_group.add_argument('-N', '--no-indent', help='Do not indent output to show dependency structure', action='store_true')

    # General
    general_group = argparser.add_argument_group('general options')
    general_group.add_argument('-D', '--dir', help='Root FITS dir (default: autodetect)')
    general_group.add_argument('-v', '--verbose', help='Increase verbosity', action='count', default=0)

    argparser.epilog = """
examples:

    Add master calibration files:
        fitscollect -o ngc300 -f V | fitscollectcalib --master-calib
        
    Add raw calibration files:
        fitscollect -o ngc300 -f V | fitscollectcalib --raw-calib
        
    Add only master zeros and darks:
        fitscollect -o ngc300 -f V | fitscollectcalib --master-zero --master-dark
        
    From file list (no stdin):
        fitscollectcalib --master-calib file1.fits file2.fits file3.fits
    """

    args = argparser.parse_args()

    # Handle umbrella flags
    if args.raw_calib:
        args.raw_zero = True
        args.raw_dark = True
        args.raw_flat = True

    if args.master_calib:
        args.master_zero = True
        args.master_dark = True
        args.master_flat = True

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

