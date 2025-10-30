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
```


