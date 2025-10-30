#!/usr/bin/python3

#####################################################################################################################
# Description 	: This script shows fits list in current folder
# Written by  	: Mirk
# Version      	: V0.1.0
# Date  	: 2025-10-29
#
# README:
# To install:
# 1. Copy file to .local/bin (file must be without extension)
# 2. Make it executable
# 3. Make sure that .local/bin is on $PATH list, if not add this folder to path
# 4. After terminal restart go to fits files folder and type: fitslist
#####################################################################################################################

import os
import re
from typing import List, Dict, Tuple, Optional


def open_file_data(file: str) -> Optional[str]:
    for n in ['cp1252', 'utf8', 'cp850']:
        try:
            with open(file, 'r', encoding=n) as f:
                return f.read(15000)
        except:
            pass
    print(f'Cannot encode {file}')
    return None

def read_fits_header(data: str) -> List:
    li = []
    for n in range(1, 200):
        dp = data[80 * (n - 1):(80 * n)]
        li.append(dp)
        if 2 > dp.find('END') > -1:
            return li
    return li

def ccd_t(dat) -> Tuple:
    try:
        a_5 = 10 - len(str(round(float(dat["CCD-TEMP"][0]), 2)))
        ccd_t = round(float(dat["CCD-TEMP"][0]), 2)
    except (ValueError, LookupError, TypeError):
        try:
            a_5 = 10 - len(str(round(float(dat["T-CAM"][0]), 2)))
            ccd_t = round(float(dat["T-CAM"][0]), 2)
        except (ValueError, LookupError, TypeError):
            ccd_t = ''
            a_5 = 10
    return ccd_t, a_5

def get_dict_header(lis: List) -> Dict:
    di = {}
    for n in lis:
        if n.find('=') > -1:
            name = n.split('=')[0]
            if name.find(' ') > -1:
                name = name.replace(' ', '')
            last = n.split('=')[1]
            if last.find('/') > -1:
                value = last.split('/')[0]
                comment = last.split('/')[1]
            else:
                value = last
                comment = ''
            if value.find(' ') > -1:
                value = value.replace(' ', '')
            if value.find("'") > -1:
                value = value.replace("'", "")
            if value.find('.') > -1:
                try:
                    value = value = float(value)
                except ValueError:
                    value = value
            else:
                try:
                    value = int(value)
                except ValueError:
                    value = value
            di[name] = [value, comment]
    return di


def get_fits_list(path: str) -> List:
    li = []
    all_f = os.listdir(path=path)
    for n in all_f:
        if re.search(r'.*.fits', n):
            li.append(n)
    li.sort()
    return li


def main():
    path = os.getcwd()
    fd = {}
    s = ' '
    ww = '-'
    w = 1

    for n in get_fits_list(path):
        f = open_file_data(os.path.join(path, n))
        h = read_fits_header(f)
        fd[n] = get_dict_header(h)
    if len(list(fd.keys())) > 0:
        if 'OCASTD' in fd[list(fd.keys())[0]].keys():
            s = ' '
            ww = '-'
            print(
                f'{"FITS NAME"}{s * 14}|{"IMAGETYP"}{s * 7}|{"EXPTIME"}{s * 3}|{"T-CAM   "}{s * 2}|{"FILTER"}{s * 4}|{"READ-MOD"}{s * 2}|{"GAIN-MOD"}{s * 2}|{"DATE-OBS"}{s * 22}|{"OBJECT"}')
            print(f'{ww * 150}')

            for m, d in fd.items():
                a0 = 23 - len(m)
                a3 = 10 - len(d["FILTER"][0])
                a4 = 30 - len(d["DATE-OBS"][0])
                try:
                    a2 = 10 - len(str(round(float(d["EXPTIME"][0]), 2)))
                    exp_time = round(float(d["EXPTIME"][0]), 2)
                except (ValueError, KeyError):
                    a2 = 10
                    exp_time = ''
                try:
                    ver = int(d['OCASTD'][0].split('.')[0])
                except ValueError:
                    ver = str(d['OCASTD'][0])
                if ver == 1:
                    ccd_temp, a5 = ccd_t(dat=d)
                    a6 = 10 - len(str(d["READ-MOD"][0]))
                    a7 = 10 - len(str(d["GAIN-MOD"][0]))
                    a1 = 15 - len(d["IMAGETYP"][0])
                    print(
                        f'{m}{s * a0}|'
                        f'{d["IMAGETYP"][0]}{s * a1}|'
                        f'{exp_time}{s * a2}|'
                        f'{ccd_temp}{s * a5}|'
                        f'{d["FILTER"][0]}{s * a3}|'
                        f'{d["READ-MOD"][0]}{s * a6}|'
                        f'{d["GAIN-MOD"][0]}{s * a7}|'
                        f'{d["DATE-OBS"][0]}{s * a4}|'
                        f'{d["OBJECT"][0]}'
                    )
                elif ver == 'BETA3':
                    ccd_temp, a5 = ccd_t(dat=d)
                    a6 = 10 - len(str(d["READ-MOD"][0]))
                    a7 = 10 - len(str(d["GAIN-MOD"][0]))
                    a1 = 15 - len(d["IMAGETYP"][0])
                    print(
                        f'{m}{s * a0}|'
                        f'{d["IMAGETYP"][0]}{s * a1}|'
                        f'{exp_time}{s * a2}|'
                        f'{ccd_temp}{s * a5}|'
                        f'{d["FILTER"][0]}{s * a3}|'
                        f'{d["READ-MOD"][0]}{s * a6}|'
                        f'{d["GAIN-MOD"][0]}{s * a7}|'
                        f'{d["DATE-OBS"][0]}{s * a4}|'
                        f'{d["OBJECT"][0]}'
                    )
                elif ver == 'BETA2':

                    a1 = 15 - len(d["OBSTYPE"][0])
                    ccd_temp, a5 = ccd_t(dat=d)
                    a6 = 10 - len(str(d["READ_MOD"][0]))
                    a7 = 10 - len(str(d["GAIN"][0]))
                    print(
                        f'{m}{s * a0}|'
                        f'{d["OBSTYPE"][0]}{s * a1}|'
                        f'{exp_time}{s * a2}|'
                        f'{ccd_temp}{s * a5}|'
                        f'{d["FILTER"][0]}{s * a3}|'
                        f'{d["READ_MOD"][0]}{s * a6}|'
                        f'{d["GAIN"][0]}{s * a7}|'
                        f'{d["DATE-OBS"][0]}{s * a4}|'
                        f'{d["OBJECT"][0]}'
                    )
                else:
                    print(f'WARNING: Unknown fits header format {m}')
        else:
            print(
                f'{s * w}{"FITS NAME":45}|'
                f'{s * w}{"FRAME":8}|'
                f'{s * w}{"EXPTIME":8}|'
                f'{s * w}{"CCD-TEMP":9}|'
                f'{s * w}{"BINX-BINY":11}|'
                f'{s * w}{"GAIN":8}|'
                f'{s * w}{"OFFSET":8}|'
                f'{s * w}{"FOCUSPOS":9}|'
                f'{s * w}{"FOCUSTEM":9}|'
                f'{s * w}{"DATE-OBS":25}|'
                f'{s * w}{"OBJECT":45}')
            print(f'{ww * 170}')
            for m, d in fd.items():
                try:
                    print(
                        f'{s * w}{m:45}|'
                        f'{s * w}{d["FRAME"][0]:8}|'
                        f'{s * w}{str(round(float(d["EXPTIME"][0]), 2)):8}|'
                        f'{s * w}{str(round(float(d["CCD-TEMP"][0]), 2)):9}|'
                        f'{s * w}{str(str(d["XBINNING"][0]) + "x" + str(d["YBINNING"][0])):11}|'
                        f'{s * w}{str(d["GAIN"][0]):8}|'
                        f'{s * w}{str(d["OFFSET"][0]):8}|'
                        f'{s * w}{str(d["FOCUSPOS"][0]):9}|'
                        f'{s * w}{str(d["FOCUSTEM"][0]):9}|'
                        f'{s * w}{d["DATE-OBS"][0]:25}|'
                        f'{s * w}{d["OBJECT"][0]:45}'
                    )
                except (KeyError, IndexError):
                    print(f'{s * w}{m:45} UNKNOWN FITS HEADER FORMAT')
    else:
        print("NO FITS FILES")

if __name__ == "__main__":
    main()
