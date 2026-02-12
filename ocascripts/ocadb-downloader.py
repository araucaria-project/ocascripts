#!/usr/bin/env python

import sys
import os
import http.client
import ssl
import json
import argparse
import requests

class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    INPROGRESS = WARNING+"IN PROGRESS"+ENDC
    DONE = OKGREEN+"   DONE!   "+ENDC
    ERROR = FAIL+"   ERROR   "+ENDC

def ping_ocadb_service():
    service_url = 'https://ocadb.onrender.com'

    print("["+bcolors.INPROGRESS+f"]\tWaiting for OCADB service do be up... (it might take a while)", end="", flush=True, file=sys.stderr)
    resp = requests.get(service_url)

    if resp.status_code == 200:
        print("\r["+bcolors.DONE+f"]\tWaiting for OCADB service do be up... (it might take a while)", file=sys.stderr)
    else:
        print("\r["+bcolors.ERROR+f"]\tWaiting for OCADB service do be up... (it might take a while)", file=sys.stderr)
        print("The service failed. Exiting...", file=sys.stderr)
        exit(1)

def refresh_jwt(user, password):
    login_uri = 'https://ocadb.onrender.com/api/v1/auth/token'
    body = f"username={user}&password={password}&grant_type=password"
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    jwt = ""

    print("["+bcolors.INPROGRESS+f"]\tAccessing OCADB with username and password", end="", flush=True, file=sys.stderr)

    resp = requests.post(login_uri, data=body, headers=headers)

    if resp.status_code == 200:
        jwt = json.loads(resp.content.decode())["access_token"]
        print("\r["+bcolors.DONE+f"]\tAccessing OCADB with username and password", file=sys.stderr)
    elif resp.status_code == 401:
        print("\r["+bcolors.DONE+f"]\tAccessing OCADB with username and password", file=sys.stderr)
        print("Wrong credentials. Exiting...", file=sys.stderr)
        exit(1)

    return jwt

def list_all_fits(jwt, username, password):
    list_all_url = f"https://ocadb.onrender.com/api/v1/observations"
    headers = {'Authorization' : f'Bearer {jwt}'}

    print("[" + bcolors.INPROGRESS + f"]\tListing all observations", end="",
          flush=True, file=sys.stderr)

    resp = requests.get(list_all_url, headers=headers)

    if resp.status_code == 200:
        obs_list = json.loads(resp.content.decode())
        print("\r[" + bcolors.DONE + f"]\tListing all observations", flush=True, file=sys.stderr)
        for obs in range(len(obs_list)):
            print(f"{obs_list[obs]['filename']}", flush=True)

        print(f"[" + bcolors.DONE + f"]\t{len(obs_list)} FITS files listed.", file=sys.stderr)

def find_fits(filename, jwt, username, password):
    find_filename_url = f"https://ocadb.onrender.com/api/v1/observations/by-filename/{filename}"
    headers = {'Content-Type': 'application/x-www-form-urlencoded', 'Authorization': f'Bearer {jwt}'}

    print("[" + bcolors.INPROGRESS + f"]\tFinding FITS file with name {filename}", end="",
          flush=True, file=sys.stderr)

    max_retries = 3
    while (True):
        resp = requests.get(find_filename_url, headers=headers)
        if resp.status_code == 200:
            print("\r[" + bcolors.DONE + f"]\tFinding FITS file with name {filename}", file=sys.stderr)
            obs_found = json.loads(resp.content.decode())
            print(json.dumps(obs_found, indent=3))
            break
        else:
            max_retries -= 1
            if max_retries < 0:
                print("Error while getting the file", file=sys.stderr)
                exit(1)


def get_filename_url(filename, jwt, username, password):
    jwt = jwt

    find_filename_url = f"https://ocadb.onrender.com/api/v1/observations/by-filename/{filename}/url"
    headers = {'Content-Type': 'application/x-www-form-urlencoded', 'Authorization' : f'Bearer {jwt}'}

    max_retries = 3
    while(True):
        resp = requests.get(find_filename_url, headers=headers)
        if resp.status_code == 200:
            return json.loads(resp.content.decode())[0]["description"], json.loads(resp.content.decode())[0]["url"], jwt
        elif resp.status_code == 401:
            jwt = refresh_jwt(username, password)
        else:
            max_retries -= 1
            if max_retries < 0:
                print("Error while getting the file", file=sys.stderr)
                exit(1)

def get_batch_filename_urls(filenames, jwt, username, password):
    jwt = jwt

    get_batch_urls_url = f"https://ocadb.onrender.com/api/v1/observations/by-batch-filename/url"
    headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {jwt}'}
    body = json.dumps(filenames)

    print("[" + bcolors.INPROGRESS + f"]\tGetting download urls from OCADB", end="",
          flush=True, file=sys.stderr)

    urls = []
    max_retries = 3
    while (True):
        resp = requests.post(get_batch_urls_url, data=body, headers=headers)
        if resp.status_code == 200:
            # return json.loads(resp.content.decode())[0]["description"], json.loads(resp.content.decode())[0]["url"], jwt
            fits_urls = json.loads(resp.content.decode())
            urls = [(file["description"], file["url"]) for file in fits_urls]
            print("\r[" + bcolors.DONE + f"]\tGetting download urls from OCADB",
                  flush=True, file=sys.stderr)
            return urls, jwt
        elif resp.status_code == 401:
            jwt = refresh_jwt(username, password)
        else:
            max_retries -= 1
            if max_retries < 0:
                print(resp.status_code)
                print("Error while getting the file", file=sys.stderr)
                exit(1)

def download_fits(url, filename, i, n):
    local_filename = f"{filename}.part"
    print(f"["+bcolors.INPROGRESS+f"]\tDownloading {filename} [{i+1}/{n}]", end="", flush=True, file=sys.stderr)
    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        with open(local_filename, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)

    os.rename(local_filename, filename)
    print(f"\r["+bcolors.DONE+f"]\tDownloading {filename} [{i+1}/{n}]", flush=True, file=sys.stderr)
    return filename


def main() -> int:
    parser = argparse.ArgumentParser(
        prog='OCADB-Downloader',
        description='Downloads fits files from OCADB, based on STDIN input.',
        epilog='Saves the downloaded files to the current folder, lists all available FITS files, finds and displays info using FITS filename.')

    # parser.add_argument('username')  # positional argument
    parser.add_argument('-u', '--username', help='OCADB Username')
    parser.add_argument('-p', '--password', help='OCADB Password')
    parser.add_argument('-l', '--list', help="List all available observations", action='store_true')
    parser.add_argument('-f', '--filename', help='Find FITS by filename')
    parser.add_argument('--chunksize', type=int, default=40, help='Chunk size for getting download links from OCADB. Default = 40')

    args = parser.parse_args()

    api_url = "ocadb.onrender.com"

    ping_ocadb_service()
    jwt = refresh_jwt(args.username, args.password)

    if args.list:
        list_all_fits(jwt, args.username, args.password)
    elif args.filename:
        find_fits(args.filename, jwt, args.username, args.password)
    else:
        files_queue = []
        for line in sys.stdin:
            files_queue.append(os.path.basename(line.strip()))

        # chunks
        chunk_size = args.chunksize
        url_chunks = [files_queue[i:i + chunk_size] for i in range(0, len(files_queue), chunk_size)]

        file_no = 0
        for chunk in range(len(url_chunks)):
            file_urls_list, jwt = get_batch_filename_urls(url_chunks[chunk], jwt, args.username, args.password)

            for url_tuple in range(len(file_urls_list)):
                download_fits(file_urls_list[url_tuple][1], file_urls_list[url_tuple][0], file_no, len(files_queue))
                file_no += 1

        # single shots
        # for file in range(len(files_queue)):
        #     filename, url, jwt = get_filename_url(files_queue[file], jwt, args.username, args.password)
        #     download_fits(url, filename, file, len(files_queue))

if __name__ == '__main__':
    ret_code = main()
    exit(ret_code)