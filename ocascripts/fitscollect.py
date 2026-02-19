"""Collects OCA FITS files according to specified criteria.
Returns a list of FITS files paths or names.

This script works fast because it iterates over processed files directories instead of
filtering individual files, thus only files known to OFP are considered, namely only files
having corresponding JSON counterpart are considered:
   {telescope}/processed-ofp/targets/{object}/{filter}/light-curve/{telescope}?_????_?????.json

For science files, the script returns ZDF calibrated files by default. Use --raw to add
raw science files to the output. Use --exclude-zdf to exclude ZDF files from output.

v. 1.0.0
"""
import argparse
import logging
import re
import signal
import sys
from pathlib import Path
from argparse import ArgumentParser, Namespace
from typing import Optional, Tuple
import datetime


log = logging.getLogger('collect')

def ocm_julian_date(date: datetime.date) -> int:
    """
    Calculate 4dig OCA Julian Date for a given date.
    """
    # ref date is 2023-02-23

    return date.toordinal() - 738574 # 738574 is 2023-02-23

def ensure_oca_julian(dt: Optional[str]) -> int:
    try:
        return int(dt)
    except ValueError:
        # iso -> date -> julian -> -2460000
        try:
            dt = ocm_julian_date(datetime.date.fromisoformat(dt))
        except Exception:
            log.error(f'Invalid date: {dt}')
            raise ValueError(f'Invalid date: {dt}')
    return int(dt)

RET_T = Tuple[Optional[str], Optional[str], Optional[str]]
RET_NULL = (None, None, None)


def process_path(root_path: Path, path: Path, args: Namespace, date_range: Tuple[int, int]) -> RET_T:
    """Process a single observation and output files."""
    basename = path.stem
    try:
        # Extract oca julian day string and telescope from path:
        # e.g. "0671" and "jk15" from jk15c_0671_62637.json
        m = re.match(r'(?P<telescope>\w{4})(?P<instr>.)_(?P<night>\d{4})_(?P<count>\d{5}).json', path.name)
        night = m.group('night')
        telescope = m.group('telescope')
        instr = m.group('instr')
    except Exception as e:
        log.error(f'Invalid filename: {path}, can not extract night: {e}')
        return RET_NULL

    if int(night) < date_range[0] or int(night) > date_range[1]:
        return RET_NULL

    # Add raw science files if requested
    if args.raw:
        fits_path = root_path / telescope / 'raw' / night / f'{basename}.fits'
        if args.check and not fits_path.exists():
            log.warning(f'File {fits_path} does not exist')
        else:
            if args.name:
                print(fits_path.name)
            else:
                print(fits_path)

    # Add ZDF (calibrated) science files unless excluded
    if not args.exclude_zdf:
        fits_path = root_path / telescope / 'processed-ofp' / 'science' / night / basename / f'{basename}_zdf.fits'
        if args.check and not fits_path.exists():
            log.warning(f'File {fits_path} does not exist')
        else:
            if args.name:
                print(fits_path.name)
            else:
                print(fits_path)

    return telescope, night, instr







def main() -> int:
    # command line arguments
    argparser = ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)

    # Filtering options group
    filter_group = argparser.add_argument_group('filtering options', 'Criteria for selecting FITS files')
    filter_group.add_argument('-o', '--object', help='Object name spelled identical to objet\'s field directory name', metavar='TARGET', default='*')
    filter_group.add_argument('-t', '--telescope', help='Telescope name', metavar='TEL', default='*')
    filter_group.add_argument('-f', '--filter', help='Filter name', default='*')
    # date, may have one or two arguments - start and end or just specific date.
    # May have form od ISO date or OCA Julian date
    filter_group.add_argument('-d', '--date', nargs='+',
                           help='UT night start date (single arg) or date range (two args), in ISO or OCA Julian date format')

    # Content selection group
    content_group = argparser.add_argument_group('content selection', 'Select which types of files to include')
    content_group.add_argument('-Z', '--exclude-zdf', help='Exclude ZDF calibrated science images', action='store_true')
    content_group.add_argument('-r', '--raw', help='Include raw science files (in addition to ZDF, unless --exclude-zdf)', action='store_true')
    content_group.add_argument('-c', '--check', help='Check if FITS file exists in filesystem before returning its name/path', action='store_true')

    # Output format group
    format_group = argparser.add_argument_group('output format', 'Control output presentation')
    format_group.add_argument('-n', '--name', help='Print filenames only instead of abs paths', action='store_true')

    # General options group
    general_group = argparser.add_argument_group('general options')
    general_group.add_argument('-D', '--dir', help='Root FITS dir, default: autodetect', default=None)
    general_group.add_argument('-v', '--verbose', help='-v gives some stats, -vv search pattern for debugging', action='count', default=0)
    # examples
    argparser.epilog = """
examples:

    Output names of calibrated ZDF FITS of target 'ngc300-center' in Ic:
        fitscollect -o ngc300-center -f Ic -n -v
        
    Copy all raw science FITS files (excluding ZDF) to /tmp/myfits:
        fitscollect -o ngc300-center --raw --exclude-zdf | xargs -I {} cp {} /tmp/myfits
        
    Output both ZDF and raw science files:
        fitscollect -o ngc300-center --raw
        
    Symlink all ZDF files from date range:
        fitscollect -t zb08 -d 2024-01-01 2024-01-31 | xargs -I {} ln -s {} /tmp/myfits
    """


    args: Namespace = argparser.parse_args()


    # Allow default SIGPIPE handling on Unix to avoid BrokenPipeError tracebacks.
    try:
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    except (AttributeError, ValueError):
        # SIGPIPE may be unsupported or disallowed in some environments.
        pass

    log_format = '%(asctime)s [%(levelname)s] [%(name)s] %(message)s'
    if args.verbose == 1:
        logging.basicConfig(level=logging.INFO, format=log_format)
    elif args.verbose > 1:
        logging.basicConfig(level=logging.DEBUG, format=log_format)
    else:
        logging.basicConfig(level=logging.WARNING, format=log_format)

    root_propositions = {
        'OCM': '/data/fits',
        'CAMK': '/work/vela/oca/fits',
        'Mik':  '/Users/Shared/oca_data/fits'
    }

    if args.dir is not None:
        root_path = Path(args.dir)
        if not root_path.is_dir():
            log.error(f'Root FITS dir {root_path} not found')
            return -1
    else:
        root_path = None
        for s, p in root_propositions.items():
            p = Path(p)
            if p.is_dir():
                log.info(f'Autodetect dir schema {s}, root FITS dir: {p}')
                root_path = p
                break
        if root_path is None:
            log.error('No root FITS dir found. Autodetect failed. Please specify root FITS dir with --dir argument.')
            return -1

    # dates: determine start_date, end_date in 4dig julian (OCA julian):
    # - if no date specified, use all dates
    if args.date is None:
        start_date = 0
        end_date = 9999
    else:
        if len(args.date) == 1:
            start_date = end_date = args.date[0]
        elif len(args.date) == 2:
            start_date, end_date = args.date
        else:
            log.error('Invalid date argument')
            return -1
        try:
            start_date = ensure_oca_julian(start_date)
            end_date = ensure_oca_julian(end_date)
        except Exception as e:
            log.error(f'Invalid date argument: {args.date} {e}')
            return -1
        if start_date < 0:
            log.warning(f'Date value, before modern OCA era: start={start_date}')
            start_date = 0
        if end_date < 0:
            log.warning(f'Date value, before modern OCA era: end={end_date}')
            end_date = 0
        if start_date > 9999:
            log.warning(f'Date value later than 2050-07-11 not fully supported, start={start_date}')
            start_date = 9999
        if end_date > 9999:
            log.warning(f'Date value later than 2050-07-11 not fully supported, end={end_date}')
            end_date = 9999
        if start_date > end_date:
            log.warning(f'Empty date range: {start_date} > {end_date}')
            return 0 # formally it's not forbidden, but still nothing to do

    log.debug(f'Filtering:')
    log.debug(f'  Start date: {start_date}')
    log.debug(f'  End date: {end_date}')
    log.debug(f'  Telescope: {args.telescope}')
    log.debug(f'  Target: {args.object}')
    log.debug(f'  Filter: {args.filter}')

    glob_pattern = (f'{args.telescope}/processed-ofp/targets/{args.object.lower()}/{args.filter}'
                    f'/light-curve/{args.telescope}?_????_?????.json'
                    )
    log.debug(f'Glob pattern: {glob_pattern}')
    count = 0
    telescopes = set()
    nigts = set()
    instrs = set()
    filters = set()

    for path in root_path.glob(glob_pattern):
        telescope, night, instr = process_path(
            root_path=root_path,
            path=path,
            args=args,
            date_range=(start_date, end_date)
        )
        if (telescope, night, instr) == RET_NULL:
            continue
        count += 1
        flt = path.parts[-3]
        telescopes.add(telescope)
        nigts.add(night)
        instrs.add(instr)
        filters.add(flt)

    log.info(f'Observations found: {count} taken in {len(nigts)} nights')
    log.info(f'Involved telescopes: {telescopes}, instruments: {instrs}, filters: {filters}')

    return 0




if __name__ == "__main__":
    try:
        ret_code = main()
        exit(ret_code)
    except BrokenPipeError:
        # Exit quietly when the pipe is closed by the consumer.
        try:
            sys.stdout.close()
        finally:
            exit(0)
