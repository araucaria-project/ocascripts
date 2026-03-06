"""Displays FITS file headers in tabular format.

Takes a list of FITS files (from stdin or positional arguments) and displays
their headers as a table - like fitslist, but reading files from a list
instead of scanning current directory.

Files can be provided as full paths or just basenames. Basenames are resolved
to their canonical paths using the OCA FITS directory structure.

The first column shows either the full path (default) or just the basename (-n option).

v. 1.0.0
"""
import argparse
import logging
import signal
import sys
from pathlib import Path
from argparse import ArgumentParser
from typing import Optional, List, Dict, Tuple, Callable

from ocafitsfiles import detect_fits_root, parse_filename, canonical_path

PATH_COL = 103

log = logging.getLogger('collectlist')


def read_fits_header(path: Path) -> Optional[Dict]:
    """Read and parse FITS header from file, return dict of key -> (value, comment)."""
    for encoding in ['cp1252', 'utf8', 'cp850']:
        try:
            with open(path, 'r', encoding=encoding) as f:
                data = f.read(15000)
            break
        except Exception:
            continue
    else:
        log.warning(f'Cannot read {path}')
        return None

    # Parse header cards (each 80 chars)
    header = {}
    for i in range(200):
        card = data[80 * i:80 * (i + 1)]
        if card[:3] == 'END':
            break
        if '=' not in card:
            continue
        key, rest = card.split('=', 1)
        key = key.strip()
        value, _, comment = rest.partition('/')
        value = value.strip().strip("'").strip()
        # Try numeric conversion
        try:
            value = int(value)
        except ValueError:
            try:
                value = float(value)
            except ValueError:
                pass
        header[key] = (value, comment.strip())

    return header


def resolve_path(file_input: str, root: Optional[Path] = None) -> Tuple[Optional[Path], str]:
    """Resolve a file input (name or path) to canonical path and display string.

    Args:
        file_input: Either a full path or just a basename (with or without .fits extension)
        root: Root directory for FITS files (auto-detected if None)

    Returns:
        Tuple of (canonical_path, display_string) where display_string is the name or path
        depending on context. Returns (None, input) if resolution fails.
    """
    if root is None:
        schema, root = detect_fits_root()
        if not schema:
            return None, file_input

    # Try as-is first (might be a full path)
    p = Path(file_input)
    if p.is_file():
        return p, file_input

    # Try as basename - resolve to canonical path
    basename, suffix = parse_filename(file_input)
    if basename:
        try:
            canonical = canonical_path(basename, suffix, root)
            if canonical.exists():
                return canonical, file_input
        except Exception:
            pass

    return None, file_input


def ccd_temp(header: Dict) -> str:
    """Extract CCD temperature from header."""
    for key in ('CCD-TEMP', 'T-CAM'):
        if key in header:
            try:
                return str(round(float(header[key][0]), 2))
            except (ValueError, TypeError):
                pass
    return ''


def _fmt_exptime(header: Dict) -> str:
    return str(round(float(header.get("EXPTIME", (0,))[0]), 2))


def _fmt_binning(header: Dict) -> str:
    return f'{header.get("XBINNING", ("?",))[0]}x{header.get("YBINNING", ("?",))[0]}'


def _compute_widths(columns: List[Tuple[str, Callable[[Dict], object]]], rows: List[Tuple[str, Dict]]) -> Dict[str, int]:
    """Compute compact column widths with one trailing space after longest value."""
    widths = {name: len(name) for name, _ in columns}
    for path, h in rows:
        widths['PATH'] = max(widths.get('PATH', len('PATH')), len(path))
        if not h:
            continue
        for name, getter in columns:
            if name == 'PATH':
                continue
            try:
                value = getter(h)
            except Exception:
                continue
            widths[name] = max(widths[name], len(str(value)))
    # Keep one extra space before the separator for readability.
    return {name: w + 1 for name, w in widths.items()}


def _build_commented_header(columns: List[Tuple[str, Callable[[Dict], object]]], widths: Dict[str, int]) -> str:
    """Build commented header without shifting separator positions vs data rows."""
    parts = []
    for idx, (name, _) in enumerate(columns):
        width = widths[name]
        # Leading '#' consumes one character; compensate in first column width.
        if idx == 0 and width > 1:
            width -= 1
        parts.append(f'{name:<{width}}')
    return '#' + '|'.join(parts)


def _print_with_layout(rows: List[Tuple[str, Dict]], columns: List[Tuple[str, Callable[[Dict], object]]]):
    widths = _compute_widths(columns, rows)

    header_line = _build_commented_header(columns, widths)
    print(header_line)
    print('#' + ('-' * (len(header_line) - 1)))

    for path, h in rows:
        if not h:
            print(f'{path:<{widths["PATH"]}}| UNREADABLE')
            continue
        try:
            out = []
            for name, getter in columns:
                value = str(getter(h) if name != 'PATH' else path)
                out.append(f'{value:<{widths[name]}}')
            print('|'.join(out))
        except Exception as e:
            print(f'{path:<{widths["PATH"]}}| ERROR: {e}')


def _print_ocastd(rows: List[Tuple[str, Dict]]):
    """Print table for OCA standard (OCASTD) FITS files."""
    columns = [
        ('PATH', lambda _h: ''),
        ('IMAGETYP', lambda h: h.get('IMAGETYP', ('',))[0]),
        ('EXPTIME', _fmt_exptime),
        ('T-CAM', ccd_temp),
        ('FILTER', lambda h: h.get('FILTER', ('',))[0]),
        ('SCIPROG', lambda h: h.get('SCIPROG', ('',))[0]),
        ('PI', lambda h: h.get('PI', ('',))[0]),
        ('DATE-OBS', lambda h: h.get('DATE-OBS', ('',))[0]),
        ('OBJECT', lambda h: h.get('OBJECT', ('',))[0]),
    ]
    _print_with_layout(rows, columns)


def _print_generic(rows: List[Tuple[str, Dict]]):
    """Print table for generic FITS files."""
    columns = [
        ('PATH', lambda _h: ''),
        ('FRAME', lambda h: h.get('FRAME', ('',))[0]),
        ('EXPTIME', _fmt_exptime),
        ('CCD-TEMP', lambda h: str(round(float(h.get('CCD-TEMP', (0,))[0]), 2))),
        ('BIN', _fmt_binning),
        ('GAIN', lambda h: h.get('GAIN', ('',))[0]),
        ('DATE-OBS', lambda h: h.get('DATE-OBS', ('',))[0]),
        ('OBJECT', lambda h: h.get('OBJECT', ('',))[0]),
    ]
    _print_with_layout(rows, columns)


def print_table(rows: List[Tuple[str, Dict]]):
    """Print rows as formatted table, auto-detecting header format."""
    if not rows:
        print('NO FITS FILES')
        return

    first_header = next((h for _, h in rows if h), None)
    if first_header is None:
        print('NO READABLE FITS FILES')
        return

    if 'OCASTD' in first_header:
        _print_ocastd(rows)
    else:
        _print_generic(rows)




def process_files(file_list: List[str], names_only: bool = False):
    """Process list of files and output as table.

    Args:
        file_list: List of file paths or basenames
        names_only: If True, display only filenames instead of full paths
    """
    schema, root = detect_fits_root()

    rows = []
    for line in file_list:
        path_str = line.strip()
        if not path_str:
            continue

        # Resolve input to canonical path
        resolved_path, original_input = resolve_path(path_str, root)

        if resolved_path is None or not resolved_path.is_file():
            log.warning(f'Cannot resolve: {path_str}')
            rows.append((path_str, None))
            continue

        # Read header
        header = read_fits_header(resolved_path)

        # Determine display string
        if names_only:
            display_str = resolved_path.name
        else:
            display_str = str(resolved_path)

        rows.append((display_str, header))

    print_table(rows)


def main() -> int:
    argparser = ArgumentParser(description=__doc__,
                               formatter_class=argparse.RawDescriptionHelpFormatter)

    argparser.add_argument('files', nargs='*', help='FITS files (reads from stdin if not provided)')
    argparser.add_argument('-n', '--names', help='Print filenames only, not full paths', action='store_true')
    argparser.add_argument('-v', '--verbose', action='count', default=0)

    argparser.epilog = """
examples:

    fitscollect -o ngc300 -f V | fitscollectlist
    fitscollectlist /work/vela/oca/fits/zb08/raw/0571/*.fits
    fitscollectlist -n zb08c_0571_24540.fits zb08c_0755_60589_zdf.fits
    fitscollect -o ngc300 -f V | fitscollectlist -n
    """

    args = argparser.parse_args()

    try:
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    except (AttributeError, ValueError):
        pass

    log_format = '%(asctime)s [%(levelname)s] [%(name)s] %(message)s'
    if args.verbose == 1:
        logging.basicConfig(level=logging.INFO, format=log_format)
    elif args.verbose > 1:
        logging.basicConfig(level=logging.DEBUG, format=log_format)
    else:
        logging.basicConfig(level=logging.WARNING, format=log_format)

    file_list = args.files if args.files else sys.stdin.readlines()
    process_files(file_list, names_only=args.names)

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

