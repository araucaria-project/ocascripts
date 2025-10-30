#!/usr/bin/python3

#####################################################################################################################
# Description 	: This script shows fits header (without astropy)
# Written by  	: Mirk
# Version      	: V0.1.0
# Date  	: 2025-10-29
#
# README:
# To install:
# 1. Copy file to .local/bin (must be without extension)
# 2. Make it executable
# 3. Make sure that .local/bin is on $PATH list, if not add this folder to path
# 4. After terminal restart type: fitsheader path/to/fits/file.fits
#####################################################################################################################


import os
from typing import List, Dict, Optional
import sys


def open_file_data(file: str) -> Optional[str]:
    for n in ['cp1252', 'utf8', 'cp850']:
        try:
            with open(file, 'r', encoding=n) as fi:
                return fi.read(15000)
        except (FileNotFoundError, FileExistsError):
            print(f'File not found')
            return None
        except UnicodeDecodeError:
            pass
    print(f'Cannot encode {file}')
    return None


def read_fits_header(data: str) -> List:
    li = []
    for n in range(1, 500):
        dp = data[80 * (n - 1):(80 * n)]
        li.append(dp)
        if not 'EXTEND' in dp:
            if dp.find('END') > -1:
                return li
    return li


def get_dict_header(lis: List) -> Dict:
    di = {}
    for row in lis:
        if row.find('=') > -1:
            eq_split = row.split('=')
            name = eq_split[0]
            if name.find(' ') > -1:
                name = name.replace(' ', '')

            # Looking for value
            if len(eq_split) == 2:
                val_comm = eq_split[1]
            elif len(eq_split) > 2:
                val_comm = row.replace(eq_split[0], "")
            else:
                val_comm = ""

            if val_comm.find('/') > -1:
                value = val_comm.split('/')[0]
                s = len(value) + 2
                comment = val_comm[s:]
            else:
                value = val_comm
                comment = ''

            if value.find(' ') > -1:
                value = value.replace(' ', '')
            if '=' in value:
                value = value.replace('=', '')
            if value.find("'") > -1:
                value = value.replace("'", "")
            if value.find('.') > -1:
                try:
                    value = float(value)
                except ValueError:
                    value = value
            else:
                try:
                    value = int(value)
                except ValueError:
                    value = value
            di[name] = [value, comment]
        else:
            name = row
            if name.find(' ') > -1:
                name = name.replace(' ', '')
            di[name] = None
    return di


def print_line(n, m):
    if m is not None:
        z = ' '
        a1 = 8 - len(n)
        a2 = 30 - len(str(m[0]))
        print(f'{n}{a1*z}= {2*z}{m[0]}{a2*z} / {m[1]}')
    else:
        print(f'{n}')

def main():
    ar = sys.argv
    path = os.getcwd()
    if len(ar) > 1:
        f = open_file_data(os.path.join(path, ar[1]))
        if f is not None:
            h = read_fits_header(f)
            d = get_dict_header(h)
            for p, q in d.items():
                print_line(p, q)

if __name__ == '__main__':
    main()