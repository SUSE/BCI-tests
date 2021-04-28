import argparse
import subprocess

from matryoshka_tester.data import containers


# Do real stuff
def pull_container(url):
    """ Pulls the container given in url with docker CLI """
    subprocess.check_call(["docker", "pull", url])


# DRY
def per_containertype(method):
    parser = argparse.ArgumentParser()
    parser.add_argument("container_type", help="One of the container types")
    arg = parser.parse_args()
    if arg.container_type in containers:
        for version in containers[arg.container_type]:
            method(arg.container_type, version)


def list_containertype_versions(containertype, version):
    print(version)


def fetch_versions(containertype, version):
    pull_container(containers[containertype][version])


# Convenience CLI tools
def list_container_types():
    for key in containers.keys():
        print(key)


def list_all_container_versions_per_containertype():
    per_containertype(list_containertype_versions)


def fetch_all_containers_per_containertype():
    per_containertype(fetch_versions)


def fetch_container():
    parser = argparse.ArgumentParser()
    parser.add_argument("container_type", help="One of the container types")
    parser.add_argument("container_version", help="One of the container versions for the container type")
    args = parser.parse_args()
    url = containers.get(args.container_type, {}).get(args.container_version, "")
    if url != "":
        pull_container(url)


def run():
    pass




def run_on_all_containertype_versions(containertype, method):
    pass