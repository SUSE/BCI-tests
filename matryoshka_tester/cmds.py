import argparse
import asyncio


from matryoshka_tester.data import containers
from matryoshka_tester.helpers import get_selected_runtime


from prettytable import PrettyTable


# Do real stuff
async def pull_container(url):
    """Pulls the container given in url with docker CLI"""
    cmd = f"{get_selected_runtime().runner_binary} pull {url}"
    process = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    res = await process.communicate()
    if process.returncode != 0:
        raise RuntimeError(f"command '{cmd}' failed with {process.returncode}")
    return res


# CLI
def list_containers() -> None:
    pt = PrettyTable()
    pt.field_names = ["Language", "Version", "URL"]
    pt.align = "l"
    for language, versions_list in containers.items():
        for version in versions_list:
            pt.add_row([language, version.version, version])
    print(pt)


async def fetch_containers(all_containers=False, container_type=""):
    containers_urls = []
    for language, versions_list in containers.items():
        if language == container_type or all_containers:
            for version in versions_list:
                containers_urls.append(version.full_url)
    results = await asyncio.gather(*map(pull_container, containers_urls))
    for result in results:
        print(f"[stdout]\n{result[0].decode().strip()}\n[stderr]\n{result[1].decode().strip()}")


def fetch_all_containers():
    asyncio.run(fetch_containers(all_containers=True))


def fetch_language_containers():
    parser = argparse.ArgumentParser()
    parser.add_argument("language", help="language/container type")
    arg = parser.parse_args()
    asyncio.run(fetch_containers(container_type=arg.language))
