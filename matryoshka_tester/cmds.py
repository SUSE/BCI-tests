import argparse
from pprint import pprint

from matryoshka_tester.data import containers



def fetch():
    pass

def run():
    pass

def list_container_types():
    for key in containers.keys():
        print(key)

def fetch_all():
    parser = argparse.ArgumentParser()
    parser.add_argument("container-type")
    parser.parse_args()

    pprint(containers)