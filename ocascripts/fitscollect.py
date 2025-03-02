"""Collects OCA FITS files according to specified criteria.
Returns a list of FITS files paths

Only files known to OFP are considered.
"""
import argparse
import logging
import re
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


def process_path(root_path: Path, path: Path, args: Namespace, date_range: Tuple[int, int]) -> None:
    basename = path.stem
    try:
        # extract oca julian day string and telescope from path:
        # e.g. "0671" and "jk15" from jk15c_0671_62637.json
        m = re.match(r'(?P<telescope>\w{4})(?P<instr>.)_(?P<night>\d{4})_(?P<count>\d{5}).json', path.name)
        night = m.group('night')
        telescope = m.group('telescope')
        # instr = m.group('instr')
        # count = m.group('count')
    except Exception as e:
        log.error(f'Invalid filename: {path}, can not extract night: {e}')
        return

    if int(night) < date_range[0] or int(night) > date_range[1]:
        return

    if args.raw:
        fits_path = root_path / telescope / 'raw' / night / f'{basename}.fits'
    else:
        fits_path = root_path / telescope / 'processed-ofp' / 'science' / night / basename / f'{basename}_zdf.fits'
    if args.check and not fits_path.exists():
        log.warning(f'File {fits_path} does not exist')
        return
    if args.name:
        print(fits_path.name)
    else:
        print(fits_path)







def main() -> int:
    # command line arguments
    argparser = ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    argparser.add_argument('-o', '--object', help='Object name or alias', metavar='TARGET', default='*')
    argparser.add_argument('-t', '--telescope', help='Telescope name', default='*')
    argparser.add_argument('-f', '--filter', help='Filter name', default='*')
    # date, may have one or two arguments - start and end or just specific date.
    # May have form od ISO date or OCA Julian date
    argparser.add_argument('-d', '--date', nargs='+',
                           help='Date (single arg) or date range (two args), in ISO or OCA Julian date format')
    argparser.add_argument('-r', '--raw', help='RAW files instead of calibrated ZDFs', action='store_true')
    argparser.add_argument('-n', '--name', help='Print filenames only instead of abs paths', action='store_true')
    argparser.add_argument('-c', '--check', help='Output file after checking if it exists', action='store_true')
    # argparser.add_argument('-C', '--count', help='Print count of files only', action='store_true')  # TBD
    argparser.add_argument('-D', '--dir', help='Root FITS dir, default: autodetect', default=None)
    argparser.add_argument('-v', '--verbose', action='count', default=0)
    # examples
    argparser.epilog = """
examples:

    Display names of calibrated FITS of target 'ngc300-center' in Ic:
        fitscollect -o ngc300-center -f Ic -n
        
    Copy all raw FITS files of target 'ngc300-center' to /tmp/myfits:
        fitscollect -o ngc300-center -raw | xargs  -I {} cp {} /tmp/myfits
        
    The same, but more optimal: 100 files at one 'cp', and parallel 4 'cp' processes:
        fitscollect -o ngc300-center -raw | xargs -n 100 -P 4 -I {} cp {} /tmp/myfits
        
    Symlink all ZDF files from nights 2024-01-01 to 2024-01-31, taken in zb08 telescope, to /tmp/myfits:
        fitscollect -t zb08 -d 2024-01-01 2024-01-31 | xargs -I {} ln -s {} /tmp/myfits
    """


    args: Namespace = argparser.parse_args()

    log_format = '%(asctime)s [%(levelname)s] [%(name)s] %(message)s'
    if args.verbose == 1:
        logging.basicConfig(level=logging.INFO, format=log_format)
    elif args.verbose > 1:
        logging.basicConfig(level=logging.DEBUG, format=log_format)
    else:
        logging.basicConfig(level=logging.WARNING, format=log_format)

    root_propositions = {
        'OCM': '/data/fits',
        'CAMK': '/work/apus/oca/fits',
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
                log.info(f'Dir schema {s}, root FITS dir: {p}')
                root_path = p
                break
        if root_path is None:
            log.error('No root FITS dir found')
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

    glob_pattern = (f'{args.telescope}/processed-ofp/targets/{args.object}/{args.filter}'
                    f'/light-curve/{args.telescope}?_????_?????.json'
                    )
    log.debug(f'Glob pattern: {glob_pattern}')
    for path in root_path.glob(glob_pattern):
        process_path(
            root_path=root_path,
            path=path,
            args=args,
            date_range=(start_date, end_date)
        )

    return 0




if __name__ == "__main__":
    ret_code = main()
    exit(ret_code)

