# Various scripts useful in OCA Observatory

Feel free to add yours, minimal dependencies, scripts here.

Add them to pyproject.toml as console_scripts entry points.

On the server, after `poetry install`, they will be available virtuals environment `bin` directory.

Symlink them to `/usr/local/bin` or similar location in PATH for easy access, e.g.:
```bash
sudo ln -s /home/poweruser/src/ocascripts/.venv/bin/fitscollect /usr/local/bin/fitscollect
```

## Scripts

### fitscollect
Collects OCA FITS files according to specified criteria.
Returns a list of FITS files paths.

Together with `xarg` allows copying, symlinking etc. of OCA FITS files fulfilling specified criteria.

```bash
(.venv) ~/projects/astro/ocascripts git:[master]
fitscollect --help
usage: fitscollect [-h] [-o TARGET] [-t TELESCOPE] [-f FILTER] [-d DATE [DATE ...]] [-r] [-n] [-c] [-D DIR] [-v]

Collects OCA FITS files according to specified criteria.
Returns a list of FITS files paths

Only files known to OFP are considered.

options:
  -h, --help            show this help message and exit
  -o TARGET, --object TARGET
                        Object name or alias
  -t TELESCOPE, --telescope TELESCOPE
                        Telescope name
  -f FILTER, --filter FILTER
                        Filter name
  -d DATE [DATE ...], --date DATE [DATE ...]
                        Date (single arg) or date range (two args), in ISO or OCA Julian date format
  -N NIGHT [NIGHT ...], --night NIGHT [NIGHT ...]
                        OCA night numbers to include (repeatable). Accepts integers or ISO dates.
                        ("night" is a date of the beginning of observing night)
  -r, --raw             RAW files instead of calibrated ZDFs
  -n, --name            Print filenames only instead of abs paths
  -c, --check           Output file after checking if it exists
  -D DIR, --dir DIR     Root FITS dir, default: autodetect
  -v, --verbose

examples:

    Display names of calibrated FITS of target 'ngc300-center' in Ic:
        fitscollect -o ngc300-center -f Ic -n
        
    Copy all raw FITS files of target 'ngc300-center' to /tmp/myfits:
        fitscollect -o ngc300-center -raw | xargs  -I {} cp {} /tmp/myfits
        
    The same, but more optimal: 100 files at one 'cp', and parallel 4 'cp' processes:
        fitscollect -o ngc300-center -raw | xargs -n 100 -P 4 -I {} cp {} /tmp/myfits
        
    Symlink all ZDF files from nights 2024-01-01 to 2024-01-31, taken in zb08 telescope, to /tmp/myfits:
        fitscollect -t zb08 -d 2024-01-01 2024-01-31 | xargs -I {} ln -s {} /tmp/myfits

    Collect files from specific nights only:
        fitscollect -t zb08 -N 1075 1082 1090
        fitscollect -t zb08 -N 1075 -N 1082 -o ngc300-center
```


### fitscollectlc
Collects OCA light curve files per target and/or observation programme.
Returns paths to `*_light_curve.txt` files for selected targets, telescopes and filters.

```bash
(.venv) ~/projects/astro/ocascripts
fitscollectlc --help
usage: fitscollectlc [-h] [-o TARGET] [-t TEL] [-f FILTER] [-P SCIPROG] [-n] [-A ANALYTIC_DIR] [-D DIR] [-v]

Collects OCA light curve files per target and/or observation programme.

Returns paths to *_light_curve.txt files for selected targets, telescopes and filters.

Light curve files are located at:
    {telescope}/processed-ofp/targets/{target}/{filter}/light-curve/*_light_curve.txt

When --sciprog is used, the list of targets is derived from the parquet report files
in the analytic directory (same as fitscollectparquet).

filtering options:
  -o TARGET, --object TARGET
                        Target name (directory name under targets/)
  -t TEL, --telescope TEL
                        Telescope name
  -f FILTER, --filter FILTER
                        Filter name
  -P SCIPROG, --sciprog SCIPROG
                        Science programme name (glob-style, repeatable).
                        Derives target list from parquet report files.

output format:
  -n, --name            Print filenames only instead of full paths

general options:
  -A ANALYTIC_DIR, --analytic-dir ANALYTIC_DIR
                        Analytic dir with parquet files (default: autodetect)
  -D DIR, --dir DIR     Root FITS dir (default: autodetect)
  -v, --verbose

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
```

Requires `pandas` and `pyarrow` when using `--sciprog`.

### fitscollectparquet
Lists FITS files (ZDF and/or raw) selected from the analytic parquet reports (`{tel}_report.parquet`).

```bash
fitscollectparquet [-o OBJECT] [-t TEL] [-f FILTER] [-p PI] [-P SCIPROG] [-d DATE [DATE ...]]
                   [-N NIGHT [NIGHT ...]] [--imagetyp IMAGETYP] [--min-exptime S] [--max-exptime S]
                   [--min-airmass X] [--max-airmass X] [--min-fwhm PX] [--max-fwhm PX]
                   [-T | --only-test] [-Z] [-r] [-c] [-n] [--cols COL [COL ...]] [--values COL]
                   [-A ANALYTIC_DIR] [-D DIR] [-v]
```

filtering options:

| Option | Description |
|---|---|
| `-o`, `--object OBJECT` | Object name (`OBJECT` column, glob-style, repeatable: X OR Y) |
| `-t`, `--telescope TEL` | Telescope name, repeatable |
| `-f`, `--filter FILTER` | Filter name, repeatable |
| `-p`, `--pi PI` | PI name (glob-style, repeatable) |
| `-P`, `--sciprog SCIPROG` | Science programme (glob-style, repeatable) |
| `-d`, `--date DATE [DATE]` | `DATE-OBS` UT date (`YYYY-MM-DD`): one value (single night) or two (from-to) |
| `-N`, `--night NIGHT [...]` | OCA night numbers or ISO dates (repeatable); filters by night encoded in the filename |
| `--imagetyp IMAGETYP` | `IMAGETYP` value (default: `science`) |
| `--min-exptime`, `--max-exptime` | Exposure time range |
| `--min-airmass`, `--max-airmass` | Airmass range |
| `--min-fwhm`, `--max-fwhm` | FWHM range (mean of x/y) |
| `-T`, `--include-test` | Include frames marked as test (`TEST=1`), which are **excluded by default** |
| `--only-test` | Output only frames marked as test (`TEST=1`) |

`-T` and `--only-test` are mutually exclusive. Frames with null or missing `TEST`
are treated as non-test. The test filter is applied before `--values`.

content selection:

| Option | Description |
|---|---|
| `-Z`, `--exclude-zdf` | Exclude ZDF files |
| `-r`, `--raw` | Include raw files |
| `-c`, `--check` | Check that the file exists before outputting |

output format:

| Option | Description |
|---|---|
| `-n`, `--name` | Print filenames only, not full paths |
| `--cols COL [...]` | Extra columns printed after the path (tab-separated) |
| `--values COL` | Print unique values of a column (after filtering) instead of file paths |

general options:

| Option | Description |
|---|---|
| `-A`, `--analytic-dir` | Analytic dir with parquet files (default: autodetect) |
| `-D`, `--dir` | Root FITS dir (default: autodetect) |
| `-v`, `--verbose` | Verbose output |

Examples:

```bash
fitscollectparquet -o SS_For -f r          # ZDF files, test frames skipped
fitscollectparquet -o SS_For -T            # include test frames
fitscollectparquet -o SS_For --only-test   # only test frames
fitscollectparquet -o SS_For --max-fwhm 3.0 --max-airmass 1.5
fitscollectparquet -o SS_For --cols FILTER EXPTIME AIRMASS fwhm_x
```

Requires `pandas` and `pyarrow`.

### fitscollectdownloader
Generates a self-contained shell downloader script from a file list.
Takes FITS filenames from stdin or arguments, requires OCADB username.

```bash
(.venv) ~/projects/astro/ocascripts
fitscollect -n -o ngc300 | fitscollectdownloader -u mkopernik > download.sh
fitscollectparquet -n --sciprog FT2000x | fitscollectdownloader -u mkopernik > download.sh
```

The generated script handles authentication, token refresh, and downloads via presigned URLs.

### ocadb-downloader
Allows for listing, downloading and showing corresponding OCADB information per FITS file.

```bash
usage: ocadb-downloader [-h] [-u USERNAME] [-p PASSWORD] [-l] [-f FILENAME] [--chunksize CHUNKSIZE]

Downloads fits files from OCADB, based on STDIN input.

options:
  -h, --help            show this help message and exit
  -u, --username USERNAME
                        OCADB Username
  -p, --password PASSWORD
                        OCADB Password
  -l, --list            List all available observations
  -f, --filename FILENAME
                        Find FITS by filename
  --chunksize CHUNKSIZE
                        Chunk size for getting download links from OCADB. Default = 40

Saves the downloaded files to the current folder, lists all available FITS files, finds and displays info using FITS filename.

examples:
    Download FITS files:
        cat files_to_download.txt|ocadb-downloader -u username -p password
    
        fitscollect -o object|ocadb-downloader -u username -p password
  
  
    List all FITS files available in OCADB:
        ocadb-downloader -u username -p password -l
    
    Show OCADB information per given FITS filename:
        ocadb-downloader -u username -p password -f filename.fits
    
```