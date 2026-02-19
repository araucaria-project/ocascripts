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
import re
import signal
import sys
from itertools import chain
from pathlib import Path
from argparse import ArgumentParser, Namespace
from typing import Optional, List, Tuple

log = logging.getLogger('collectcalib')


def extract_basename(file_path: str) -> Tuple[Optional[str], Optional[str]]:
    """Extract OCA basename and suffix from file path or name.

    Examples:
        /path/to/zb08c_0571_24540.fits -> zb08c_0571_24540
        zb08c_0571_24540_zdf.fits -> zb08c_0571_24540
        ../../fits/zb08c_0571_24540.fits -> zb08c_0571_24540
    """
    name = Path(file_path).name
    # Find basename, suffix ( _zdf, _master_z, etc.) and extension
    m = re.match(r'(?P<base>\w{5}.\d{4}_\d{5})(?:_(?P<suff>\w+))?\.(?P<ext>fits|fz)', name)
    if m:
        return m.group('base'), m.group('suff') if m.group('suff') else None
    return None, None


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


def find_processed_file_dir(basename: str, suffix: Optional[str], root_path: Path) -> Optional[Path]:
    """Find processed file directory for a given basename and suffix.

    e.g. for zb08c_0571_24540 and suffix zdf, returns /{root_path}/zb08/processed-ofp/science/0571/zb08c_0571_24540/
    """
    match suffix:
        case None:  # no suffix, but it still can refere to file for which ZDF exisits,
                    # so we return dir like for ZDF but only if it exists
            d = root_path / basename[:4] / 'processed-ofp' / 'science' / basename[6:10] / basename
            return d if d.is_dir() else None
        case 'zdf':
            return root_path / basename[:4] / 'processed-ofp' / 'science' / basename[6:10] / basename
        case 'master_z':
            return root_path / basename[:4] / 'processed-ofp' / 'zeros' / basename
        case 'master_d':
            return root_path / basename[:4] / 'processed-ofp' / 'darks' / basename
        case _ if suffix.startswith('master_f_'):
            fltr = suffix[len('master_f_'):]
            return root_path / basename[:4] / 'processed-ofp' / 'flats' / fltr / basename
        case _:
            return None


def find_calibration_files(level, basename: str, suffix: str, root_path: Path, args: Namespace) -> List[tuple]:
    """Find all calibration files for a given science observation.

    Returns list of (file_path, indent_level) tuples.

    Calibration dependency tree:
        ZDF / raw
        ├── master_flat ──► master_dark ──► master_zero ──► raw_zero
        │                │               └── raw_dark
        │                └── raw_flat
        ├── master_dark ──► master_zero ──► raw_zero
        │               └── raw_dark
        └── master_zero ──► raw_zero

    Recursion enters a node only if the requested file types can be found inside it:
        master_zero  → enter if: raw_zero requested
        master_dark  → enter if: master_zero, raw_zero, or raw_dark requested
        master_flat  → enter if: master_dark, master_zero, raw_zero, raw_dark, or raw_flat requested
    """
    calib_files = []

    processed_dir = find_processed_file_dir(basename, suffix, root_path)

    if processed_dir is None:
        return calib_files

    log.debug(f'Processing {basename}, suffix: {suffix}, looking in {processed_dir}')

    # iterate over all .fits or .fz files in processed_dir and find master calib files
    for f in chain(processed_dir.glob('*.fits'), processed_dir.glob('*.fz')):
        f_basename, f_suffix = extract_basename(f.name)
        if f_basename == basename and f_suffix == suffix:  # skip the original file itself
            continue
        log.debug(f'Checking file: {f}, basename: {f_basename}, suffix: {f_suffix}')
        if f_suffix is None:  # raw files have no suffix
            # Reconstruct canonical path: raw files live in /raw/{night}/, not in the
            # processed dir where the symlink is. Avoids broken/misleading symlink paths.
            night = f_basename[6:10]
            telescope = f_basename[:4]
            canonical = str(root_path / telescope / 'raw' / night / f'{f_basename}.fits')
            if suffix == 'master_z':
                if args.raw_zero:
                    calib_files.append((canonical, level + 1, 'raw_zero', f_basename, None))
            elif suffix == 'master_d':
                if args.raw_dark:
                    calib_files.append((canonical, level + 1, 'raw_dark', f_basename, None))
            elif suffix and suffix.startswith('master_f_'):
                if args.raw_flat:
                    calib_files.append((canonical, level + 1, 'raw_flat', f_basename, None))
            elif suffix == 'zdf' and f_basename == basename:
                pass  # expected: symlink to original raw science file in science dir, ignore
            else:
                log.warning(f'Unexpected RAW {f_basename} in {processed_dir}  suffix?: {suffix}')
        else:
            if f_suffix == 'master_z':
                need_inside = args.raw_zero
                if args.master_zero:
                    canonical = str(find_processed_file_dir(f_basename, f_suffix, root_path) / f.name)
                    calib_files.append((canonical, level + 1, 'master_zero', f_basename, f_suffix))
                if need_inside:
                    calib_files += find_calibration_files(level + 1, f_basename, f_suffix, root_path, args)
            elif f_suffix == 'master_d':
                need_inside = args.master_zero or args.raw_zero or args.raw_dark
                if args.master_dark:
                    canonical = str(find_processed_file_dir(f_basename, f_suffix, root_path) / f.name)
                    calib_files.append((canonical, level + 1, 'master_dark', f_basename, f_suffix))
                if need_inside:
                    calib_files += find_calibration_files(level + 1, f_basename, f_suffix, root_path, args)
            elif f_suffix.startswith('master_f_'):
                need_inside = args.master_dark or args.master_zero or args.raw_zero or args.raw_dark or args.raw_flat
                if args.master_flat:
                    canonical = str(find_processed_file_dir(f_basename, f_suffix, root_path) / f.name)
                    calib_files.append((canonical, level + 1, 'master_flat', f_basename, f_suffix))
                if need_inside:
                    calib_files += find_calibration_files(level + 1, f_basename, f_suffix, root_path, args)

    return calib_files


def process_files(file_list: List[str], args: Namespace):
    """Process list of files and output with calibration files."""
    if args.dir:
        root_path = Path(args.dir)
        if not root_path.is_dir():
            log.error(f'Provided root path is not a directory: {root_path}')
            return
        schema = 'custom'
        log.debug(f'Using provided root path: {root_path}')
    else:
        schema, root_path = detect_root_schema()
    if not schema:
        log.error('Cannot detect FITS root directory')
        return

    log.info(f'Using schema: {schema}, root: {root_path}')

    seen = set()  # for --skip-duplicates

    stats = {'source': 0, 'master_zero': 0, 'master_dark': 0, 'master_flat': 0,
             'raw_zero': 0, 'raw_dark': 0, 'raw_flat': 0, 'duplicates': 0}

    def emit(path_str: str, level: int, kind: str, dedup_basename: str, dedup_suffix: Optional[str]):
        """Output a single file, respecting --skip-duplicates. Returns True if emitted."""
        if args.skip_duplicates:
            # basename+suffix uniquely identifies a file regardless of path/symlinks
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

    # Map suffix -> stats key (used for source files only)
    def suffix_to_kind(suffix: Optional[str]) -> str:
        if suffix == 'zdf' or suffix is None:   return 'source'
        if suffix == 'master_z':                return 'master_zero'
        if suffix == 'master_d':                return 'master_dark'
        if suffix.startswith('master_f_'):      return 'master_flat'
        return 'source'

    for file_path in file_list:
        file_path = file_path.strip()
        if not file_path:
            continue

        if not args.skip_source:
            _, suf = extract_basename(file_path)
            emit(file_path, 0, suffix_to_kind(suf), file_path, None)  # source: dedup by full path
        else:
            stats['source'] += 1  # count it but don't emit

        basename, suffix = extract_basename(file_path)
        if not basename:
            log.warning(f'Cannot extract basename from: {file_path}')
            continue

        calib_files = find_calibration_files(0, basename, suffix, root_path, args)
        for calib_path, level, kind, cb, cs in calib_files:
            emit(calib_path, level, kind, cb, cs)

    total_out = sum(v for k, v in stats.items() if k != 'duplicates' and k != 'source')
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

