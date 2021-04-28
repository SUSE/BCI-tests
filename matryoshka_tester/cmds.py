import argparse
import subprocess
import asyncio


from matryoshka_tester.data import containers


from prettytable import PrettyTable


# Do real stuff
async def pull_container(url):
    """Pulls the container given in url with docker CLI"""
    process = await asyncio.create_subprocess_shell(
        "docker pull {}".format(url),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    print(f"[stdout]\n{stdout.decode().strip()}")
    print(f"[stderr]\n{stderr.decode().strip()}")


# CLI
def list_containers():
    pt = PrettyTable()
    pt.field_names = ["Language", "Version", "URL"]
    pt.align = "l"
    for language, versionsdict in containers.items():
        for version in versionsdict:
            pt.add_row([language, version, versionsdict[version]])
    print(pt)


async def fetch_containers(all_containers=False, container_type=""):
    for language, versionsdict in containers.items():
        if language == container_type or all_containers:
            for version in versionsdict:
                await asyncio.gather(pull_container(versionsdict[version]))


def fetch_all_containers():
    asyncio.run(fetch_containers(all_containers=True))


def fetch_language_containers():
    parser = argparse.ArgumentParser()
    parser.add_argument("language", help="language/container type")
    arg = parser.parse_args()
    asyncio.run(fetch_containers(container_type=arg.language))
