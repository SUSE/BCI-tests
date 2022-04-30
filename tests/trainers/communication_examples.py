""" Tests for the Python base containers, based on communication functionalities. """

import sys
import os
import time
import wget


def testwww(url, outdir):
    """Test that the simple python webserver answers to an internal get request"""

    found = False

    # get the filename from url right
    xfile = os.path.basename(url)
    print (xfile)

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

    testwww(a, b)
