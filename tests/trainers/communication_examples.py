""" Tests for the Python base containers, based on communication functionalities."""

import sys
import os
import time
import wget


def get_file_www(url, outdir):
    """This function test that the python `wget <https://pypi.org/project/wget/>`_ 
    library in the BCI is able to fetch files from a webserver.

    We use the "download" method to get a specific file from a remote url.

    Input parameters of this function are: 1) "url/xfile" , 2) "outdir", where:

    - url    : the http remote url
    - xfile  : the remote file to get
    - outdir : the directory in the container receiving xfile 

    Expected for this test: xfile present in outdir.

    """

    found = False

    # get the filename from url right
    xfile = os.path.basename(url)
    print(xfile)

    for x in range(4):
        print(f"\nN:{x} file:{xfile} ")
        try:
            filename = wget.download(url, outdir)
            if len(filename) > 0 and xfile in os.listdir(outdir):
                found = True
                break

        except Exception as e:
            print(f"\n{e} ")

        finally:
            time.sleep(4)

    if found:
        print(f"\nPASS: {xfile} received")

    else:
        raise Exception(f"FAIL: {xfile} not received")


if __name__ == "__main__":
    a = sys.argv[1]
    b = sys.argv[2]

    get_file_www(a, b)
