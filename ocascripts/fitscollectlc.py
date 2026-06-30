"""Collects OCA light curve files per target and/or observation programme.

Returns paths to *_light_curve.txt files for selected targets, telescopes and filters.

Light curve files are located at:
    {telescope}/processed-ofp/targets/{target}/{filter}/light-curve/*_light_curve.txt

When --sciprog is used, the list of targets is derived from the parquet report files
in the analytic directory (same as fitscollectparquet).

v. 1.0.0
"""
import argparse
import logging
import re
import signal
import sys
from pathlib import Path
from argparse import ArgumentParser, Namespace
from typing import Optional

import pandas as pd
from ocafitsfiles import detect_fits_root

log = logging.getLogger('collectlc')

ANALYTIC_PROPOSITIONS = [
    Path('/work/vela/oca/analytic'),
]


def detect_analytic_dir() -> Optional[Path]:
    for p in ANALYTIC_PROPOSITIONS:
        if p.is_dir():
            return p
    return None


def glob_patterns_to_fullmatch_regex(patterns: list[str]) -> str:
    """Convert simple glob patterns to a safe OR-regex for str.fullmatch."""
    return '|'.join(re.escape(p).replace(r'\*', '.*') for p in patterns)


def objects_from_parquet(analytic_dir: Path, sciprog_patterns: list[str], telescope: str) -> list[str]:
    """Return unique lowercase object names matching the given SCIPROG patterns."""

    if '*' not in telescope:
        parquet_files = [analytic_dir / f'{telescope}_report.parquet']
    else:
        parquet_files = sorted(analytic_dir.glob('*_report.parquet'))

    dfs = []
    for pf in parquet_files:
        if not pf.exists():
            log.warning(f'Parquet file not found: {pf}')
            continue
        log.info(f'Loading {pf}')
        try:
            dfs.append(pd.read_parquet(pf, columns=['OBJECT', 'SCIPROG']))
        except Exception as e:
            log.warning(f'Cannot read {pf}: {e}')

    if not dfs:
        log.error(f'No parquet files loaded from {analytic_dir}')
        return []

    df = pd.concat(dfs, ignore_index=True) if len(dfs) > 1 else dfs[0]

    pattern = glob_patterns_to_fullmatch_regex(sciprog_patterns)
    df = df[df['SCIPROG'].str.fullmatch(pattern, case=False, na=False)]

    objects = sorted({o.lower() for o in df['OBJECT'].dropna().unique()})
    log.info(f'Found {len(objects)} unique objects for SCIPROG {sciprog_patterns}')
    return objects


def main() -> int:
    argparser = ArgumentParser(description=__doc__,
                               formatter_class=argparse.RawDescriptionHelpFormatter)

    filter_group = argparser.add_argument_group('filtering options', 'Criteria for selecting light curve files')
    filter_group.add_argument('-o', '--object', help='Target name (directory name under targets/)', metavar='TARGET', default=None)
    filter_group.add_argument('-t', '--telescope', help='Telescope name', metavar='TEL', default='*')
    filter_group.add_argument('-f', '--filter', help='Filter name', default='*')
    filter_group.add_argument('-P', '--sciprog', action='append', metavar='SCIPROG',
                              help='Science programme name (glob-style, repeatable). '
                                   'Derives target list from parquet report files.')

    format_group = argparser.add_argument_group('output format')
    format_group.add_argument('-n', '--name', help='Print filenames only instead of full paths', action='store_true')

    general_group = argparser.add_argument_group('general options')
    general_group.add_argument('-A', '--analytic-dir', help='Analytic dir with parquet files (default: autodetect)', default=None)
    general_group.add_argument('-D', '--dir', help='Root FITS dir (default: autodetect)', default=None)
    general_group.add_argument('-v', '--verbose', action='count', default=0)

    argparser.epilog = """
examples:

    All light curves for target ux_car:
        fitscollectlc -o ux_car

    Light curves in B filter for all targets on telescope wk06:
        fitscollectlc -t wk06 -f B

    All light curves for targets in a science programme:
        fitscollectlc -P FT2025B-1

    Light curves in V filter for targets in a science programme:
        fitscollectlc -P FT2025B-1 -f V

    Filenames only:
        fitscollectlc -o ux_car -n
    """

    args: Namespace = argparser.parse_args()

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

    if args.dir is not None:
        root_path = Path(args.dir)
        if not root_path.is_dir():
            log.error(f'Root FITS dir {root_path} not found')
            return -1
    else:
        schema, root_path = detect_fits_root()
        if root_path is None:
            log.error('No root FITS dir found. Autodetect failed. Please specify with --dir.')
            return -1
        log.info(f'Autodetect schema {schema}, root FITS dir: {root_path}')

    # Determine object pattern(s) to glob
    if args.sciprog:
        analytic_dir = Path(args.analytic_dir) if args.analytic_dir else detect_analytic_dir()
        if not analytic_dir:
            log.error('Cannot find analytic dir. Use -A to specify.')
            return -1
        objects = objects_from_parquet(analytic_dir, args.sciprog, args.telescope)
        if not objects:
            log.warning('No objects found for the given --sciprog filter')
            return 0
        if args.object:
            obj_re = re.compile(glob_patterns_to_fullmatch_regex([args.object.lower()]))
            objects = [o for o in objects if obj_re.fullmatch(o)]
        object_patterns = objects
    else:
        object_patterns = [args.object.lower() if args.object else '*']

    log.debug(f'Object patterns ({len(object_patterns)}): {object_patterns}')
    log.debug(f'Telescope: {args.telescope}')
    log.debug(f'Filter: {args.filter}')

    count = 0
    for obj in object_patterns:
        glob_pattern = (f'{args.telescope}/processed-ofp/targets/{obj}/{args.filter}'
                        f'/light-curve/*_light_curve.txt')
        log.debug(f'Glob: {glob_pattern}')
        for path in sorted(root_path.glob(glob_pattern)):
            print(path.name if args.name else path)
            count += 1

    log.info(f'Light curve files found: {count}')
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
