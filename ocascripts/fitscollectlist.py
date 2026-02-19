"""Displays FITS file headers in tabular format.

Takes a list of FITS files (from stdin or positional arguments) and displays
their headers as a table - like fitslist, but reading files from a list
instead of scanning current directory.

Full path (as received) is shown in the first column.

v. 1.0.0
"""
import argparse
import logging
import signal
import sys
from pathlib import Path
from argparse import ArgumentParser
from typing import Optional, List, Dict, Tuple

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


def ccd_temp(header: Dict) -> str:
    """Extract CCD temperature from header."""
    for key in ('CCD-TEMP', 'T-CAM'):
        if key in header:
            try:
                return str(round(float(header[key][0]), 2))
            except (ValueError, TypeError):
                pass
    return ''


def print_table(rows: List[Tuple[str, Dict]]):
    """Print rows as formatted table, auto-detecting header format."""
    if not rows:
        print('NO FITS FILES')
        return

    # Detect format by first readable header
    first_header = next((h for _, h in rows if h), None)
    if first_header is None:
        print('NO READABLE FITS FILES')
        return

    if 'OCASTD' in first_header:
        _print_ocastd(rows)
    else:
        _print_generic(rows)


def _print_ocastd(rows: List[Tuple[str, Dict]]):
    """Print table for OCA standard (OCASTD) FITS files."""
    print(
        f'{"PATH":<{PATH_COL}}|{"IMAGETYP":<15}|{"EXPTIME":<10}|{"T-CAM":<10}|'
        f'{"FILTER":<10}|{"SCIPROG":<20}|{"PI":<20}|{"DATE-OBS":<30}|{"OBJECT"}'
    )
    print('-' * (PATH_COL + 117))

    for path, h in rows:
        if not h:
            print(f'{path:<{PATH_COL}}| UNREADABLE')
            continue
        try:
            print(
                f'{path:<{PATH_COL}}|'
                f'{str(h.get("IMAGETYP", ("",))[0]):<15}|'
                f'{str(round(float(h.get("EXPTIME", (0,))[0]), 2)):<10}|'
                f'{ccd_temp(h):<10}|'
                f'{str(h.get("FILTER", ("",))[0]):<10}|'
                f'{str(h.get("SCIPROG", ("",))[0]):<20}|'
                f'{str(h.get("PI", ("",))[0]):<20}|'
                f'{str(h.get("DATE-OBS", ("",))[0]):<30}|'
                f'{str(h.get("OBJECT", ("",))[0])}'
            )
        except Exception as e:
            print(f'{path:<{PATH_COL}}| ERROR: {e}')


def _print_generic(rows: List[Tuple[str, Dict]]):
    """Print table for generic FITS files."""
    print(
        f'{"PATH":<{PATH_COL}}|{"FRAME":<8}|{"EXPTIME":<8}|{"CCD-TEMP":<9}|'
        f'{"BIN":<6}|{"GAIN":<6}|{"DATE-OBS":<25}|{"OBJECT"}'
    )
    print('-' * (PATH_COL + 97))

    for path, h in rows:
        if not h:
            print(f'{path:<{PATH_COL}}| UNREADABLE')
            continue
        try:
            binning = f'{h.get("XBINNING", ("?",))[0]}x{h.get("YBINNING", ("?",))[0]}'
            print(
                f'{path:<{PATH_COL}}|'
                f'{str(h.get("FRAME", ("",))[0]):<8}|'
                f'{str(round(float(h.get("EXPTIME", (0,))[0]), 2)):<8}|'
                f'{str(round(float(h.get("CCD-TEMP", (0,))[0]), 2)):<9}|'
                f'{binning:<6}|'
                f'{str(h.get("GAIN", ("",))[0]):<6}|'
                f'{str(h.get("DATE-OBS", ("",))[0]):<25}|'
                f'{str(h.get("OBJECT", ("",))[0])}'
            )
        except Exception as e:
            print(f'{path:<{PATH_COL}}| ERROR: {e}')


def process_files(file_list: List[str]):
    rows = []
    for line in file_list:
        path_str = line.strip()
        if not path_str:
            continue
        path = Path(path_str)
        header = read_fits_header(path)
        rows.append((path_str, header))

    print_table(rows)


def main() -> int:
    argparser = ArgumentParser(description=__doc__,
                               formatter_class=argparse.RawDescriptionHelpFormatter)

    argparser.add_argument('files', nargs='*', help='FITS files (reads from stdin if not provided)')
    argparser.add_argument('-v', '--verbose', action='count', default=0)

    argparser.epilog = """
examples:

    fitscollect -o ngc300 -f V | fitscollectlist
    fitscollectlist /work/vela/oca/fits/zb08/raw/0571/*.fits
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
    process_files(file_list)

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


