"""Collects OCA FITS files from parquet report files.

Similar to fitscollect, but searches observations in parquet report files
instead of scanning directory structure. Provides much richer filtering options
based on all columns available in the report.

Parquet files are expected in /work/vela/oca/analytic/ (autodetected) or
specified with --analytic-dir. One file per telescope: {telescope}_report.parquet

Default output: ZDF paths (consistent with fitscollect).
Use -n for names only, -r to add raw files, -Z to exclude ZDF.

v. 1.0.0
"""
import argparse
import logging
import signal
import sys
from pathlib import Path
from argparse import ArgumentParser, Namespace
from typing import Optional

log = logging.getLogger('collectparquet')

ANALYTIC_PROPOSITIONS = [
    Path('/work/vela/oca/analytic'),
]

FITS_ROOT_PROPOSITIONS = {
    'CAMK': Path('/work/vela/oca/fits'),
    'OCM':  Path('/data/fits'),
    'Mik':  Path('/Users/Shared/oca_data/fits'),
}


def detect_analytic_dir() -> Optional[Path]:
    for p in ANALYTIC_PROPOSITIONS:
        if p.is_dir():
            return p
    return None


def detect_fits_root() -> Optional[Path]:
    for p in FITS_ROOT_PROPOSITIONS.values():
        if p.is_dir():
            return p
    return None


def zdf_path(fits_root: Path, row) -> str:
    telescope = row['TELESCOP']
    basename = row['id']
    night = basename[6:10]
    return str(fits_root / telescope / 'processed-ofp' / 'science' / night / basename / f'{basename}_zdf.fits')


def raw_path(fits_root: Path, row) -> str:
    telescope = row['TELESCOP']
    basename = row['id']
    night = basename[6:10]
    return str(fits_root / telescope / 'raw' / night / f'{basename}.fits')


def print_file(path: str, args: Namespace):
    print(Path(path).name if args.name else path)


def main() -> int:
    try:
        import pandas as pd
    except ImportError:
        log.error('pandas is required: pip install pandas pyarrow')
        return 1

    argparser = ArgumentParser(description=__doc__,
                               formatter_class=argparse.RawDescriptionHelpFormatter)

    # Filtering
    filter_group = argparser.add_argument_group('filtering')
    filter_group.add_argument('-o', '--object',    help='Object name (OBJECT column, glob-style)', default=None)
    filter_group.add_argument('-t', '--telescope', help='Telescope name (e.g. zb08)', default=None)
    filter_group.add_argument('-f', '--filter',    help='Filter name (FILTER column)', default=None)
    filter_group.add_argument('-p', '--pi',        help='PI name', default=None)
    filter_group.add_argument('-P', '--sciprog',   help='Science program (SCIPROG)', default=None)
    filter_group.add_argument('-d', '--date',      nargs='+',
                               help='DATE-OBS date range: one value (single night) or two (from-to), ISO format')
    filter_group.add_argument('--imagetyp',        help='IMAGETYP value (default: science)', default='science')
    filter_group.add_argument('--min-exptime',     help='Minimum exposure time', type=float, default=None)
    filter_group.add_argument('--max-exptime',     help='Maximum exposure time', type=float, default=None)
    filter_group.add_argument('--min-airmass',     help='Minimum airmass', type=float, default=None)
    filter_group.add_argument('--max-airmass',     help='Maximum airmass', type=float, default=None)
    filter_group.add_argument('--min-fwhm',        help='Minimum FWHM (mean of x/y)', type=float, default=None)
    filter_group.add_argument('--max-fwhm',        help='Maximum FWHM (mean of x/y)', type=float, default=None)

    # Content
    content_group = argparser.add_argument_group('content selection')
    content_group.add_argument('-Z', '--exclude-zdf', action='store_true', help='Exclude ZDF files')
    content_group.add_argument('-r', '--raw',         action='store_true', help='Include raw files')
    content_group.add_argument('-c', '--check',       action='store_true', help='Check file exists before outputting')

    # Output
    format_group = argparser.add_argument_group('output format')
    format_group.add_argument('-n', '--name', action='store_true', help='Print filenames only, not full paths')
    format_group.add_argument('--cols', nargs='+', metavar='COL',
                               help='Extra columns to print after path (tab-separated)')
    format_group.add_argument('--values', metavar='COL',
                               help='Print unique values of a column (after filtering) instead of file paths')

    # General
    general_group = argparser.add_argument_group('general options')
    general_group.add_argument('-A', '--analytic-dir', help='Analytic dir with parquet files (default: autodetect)')
    general_group.add_argument('-D', '--dir',          help='Root FITS dir (default: autodetect)')
    general_group.add_argument('-v', '--verbose',      action='count', default=0)

    argparser.epilog = """
examples:

    List ZDF files for object SS_For in filter r:
        fitscollectparquet -o SS_For -f r

    List raw files for PI bzgirski, check existence:
        fitscollectparquet -p bzgirski --raw --exclude-zdf -c

    Filter by FWHM and airmass:
        fitscollectparquet -o SS_For --max-fwhm 3.0 --max-airmass 1.5

    Print with extra columns:
        fitscollectparquet -o SS_For --cols FILTER EXPTIME AIRMASS fwhm_x

    Pipe to fitscollectlist:
        fitscollectparquet -o SS_For -f r | fitscollectlist
    """

    args = argparser.parse_args()

    try:
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    except (AttributeError, ValueError):
        pass

    log_format = '%(asctime)s [%(levelname)s] [%(name)s] %(message)s'
    if args.verbose >= 2:
        logging.basicConfig(level=logging.DEBUG, format=log_format)
    elif args.verbose == 1:
        logging.basicConfig(level=logging.INFO, format=log_format)
    else:
        logging.basicConfig(level=logging.WARNING, format=log_format)

    # Resolve dirs
    analytic_dir = Path(args.analytic_dir) if args.analytic_dir else detect_analytic_dir()
    if not analytic_dir:
        log.error('Cannot find analytic dir. Use -A to specify.')
        return 1

    fits_root = Path(args.dir) if args.dir else detect_fits_root()
    if not fits_root:
        log.error('Cannot find FITS root dir. Use -D to specify.')
        return 1

    log.info(f'Analytic dir: {analytic_dir}')
    log.info(f'FITS root: {fits_root}')

    # Determine which parquet files to load
    if args.telescope:
        parquet_files = [analytic_dir / f'{args.telescope}_report.parquet']
    else:
        parquet_files = sorted(analytic_dir.glob('*_report.parquet'))

    if not parquet_files:
        log.error(f'No parquet files found in {analytic_dir}')
        return 1

    # Build pyarrow filters for predicate pushdown (applied at read time, reduces I/O and RAM)
    # Only simple equality/range filters can be pushed down; FWHM (derived column) cannot.
    pa_filters = []
    if args.imagetyp:
        pa_filters.append(('IMAGETYP', '==', args.imagetyp))
    if args.filter:
        pa_filters.append(('FILTER', '==', args.filter))
    if args.pi:
        pa_filters.append(('PI', '==', args.pi))
    if args.sciprog:
        pa_filters.append(('SCIPROG', '==', args.sciprog))
    if args.min_exptime is not None:
        pa_filters.append(('EXPTIME', '>=', args.min_exptime))
    if args.max_exptime is not None:
        pa_filters.append(('EXPTIME', '<=', args.max_exptime))
    if args.min_airmass is not None:
        pa_filters.append(('AIRMASS', '>=', args.min_airmass))
    if args.max_airmass is not None:
        pa_filters.append(('AIRMASS', '<=', args.max_airmass))
    if args.date:
        if len(args.date) == 1:
            date_from = date_to = args.date[0]
        else:
            date_from, date_to = args.date[0], args.date[1]
        pa_filters.append(('DATE-OBS', '>=', date_from))
        pa_filters.append(('DATE-OBS', '<=', date_to + '\x7f'))  # inclusive end on string prefix

    # Load and concatenate - with predicate pushdown where possible
    dfs = []
    for pf in parquet_files:
        if not pf.exists():
            log.warning(f'Parquet file not found: {pf}')
            continue
        log.info(f'Loading {pf}')
        dfs.append(pd.read_parquet(pf, filters=pa_filters if pa_filters else None))

    if not dfs:
        log.error('No parquet files loaded')
        return 1

    df = pd.concat(dfs, ignore_index=True) if len(dfs) > 1 else dfs[0]
    log.info(f'Rows after pushdown filters: {len(df)}')

    # Post-load filters: patterns (glob/regex) and derived columns (fwhm)
    if args.object:
        df = df[df['OBJECT'].str.fullmatch(args.object.replace('*', '.*'), case=False, na=False)]

    # pi/sciprog: only re-filter if they used wildcards (otherwise already pushed down)
    if args.pi and '*' in args.pi:
        df = df[df['PI'].str.fullmatch(args.pi.replace('*', '.*'), case=False, na=False)]

    if args.sciprog and '*' in args.sciprog:
        df = df[df['SCIPROG'].str.fullmatch(args.sciprog.replace('*', '.*'), case=False, na=False)]

    if args.min_fwhm is not None or args.max_fwhm is not None:
        df = df.copy()
        df['_fwhm'] = (df['fwhm_x'] + df['fwhm_y']) / 2
        if args.min_fwhm is not None:
            df = df[df['_fwhm'] >= args.min_fwhm]
        if args.max_fwhm is not None:
            df = df[df['_fwhm'] <= args.max_fwhm]

    log.info(f'Observations after all filters: {len(df)}')

    # --values: print unique values of a column and exit
    if args.values:
        if args.values not in df.columns:
            log.error(f'Column not found: {args.values}. Available: {", ".join(df.columns)}')
            return 1
        for val in sorted(df[args.values].dropna().unique()):
            print(val)
        return 0

    # Output files
    count = 0
    skipped = 0
    for _, row in df.iterrows():
        files = []
        if args.raw:
            files.append(raw_path(fits_root, row))
        if not args.exclude_zdf:
            files.append(zdf_path(fits_root, row))

        for path in files:
            if args.check and not Path(path).exists():
                skipped += 1
                log.debug(f'File not found, skipping: {path}')
                continue
            line = Path(path).name if args.name else path
            if args.cols:
                extra = '\t'.join(str(row.get(c, '')) for c in args.cols)
                line = f'{line}\t{extra}'
            print(line)
            count += 1

    log.info(f'Files output: {count}' + (f', skipped (not found): {skipped}' if skipped else ''))
    return 0


if __name__ == '__main__':
    try:
        ret_code = main()
        exit(ret_code)
    except BrokenPipeError:
        try:
            sys.stdout.close()
        finally:
            exit(0)





