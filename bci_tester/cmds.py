import argparse
import asyncio


from bci_tester.parse_data import containers
from bci_tester.helpers import get_selected_runtime


from prettytable import PrettyTable


# Do real stuff
async def pull_container(url):
    """Pulls the container with the given url using the currently selected
    container runtime"""
    runtime = get_selected_runtime()
    process = await asyncio.create_subprocess_shell(
        f"{runtime.runner_binary} pull {url}",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    res = await process.communicate()
    if process.returncode != 0:
        raise ValueError(
            f"Could not pull container {url}, got: "
            f"returncode='{process.returncode}', "
            f"stderr='{res[1].decode().strip()}', "
            f"stdout='{res[0].decode().strip()}'"
        )

    return res


# CLI
def list_containers():
    pt = PrettyTable()
    pt.field_names = ["Name", "Language", "Version", "URL"]
    pt.align = "l"
    for container in containers:
        # TODO: Make url easier
        pt.add_row(
            [
                container.name,
                container.type,
                container.version,
                container.url,
            ]
        )
    print(pt)


async def fetch_containers(all_containers=False, container_type=""):
    # TODO: Change json decoder to have a container type, for which we can have a method to produce the url.
    containers_urls = [
        container.url
        for container in containers
        if container.type == container_type or all_containers
    ]
    results = await asyncio.gather(*map(pull_container, containers_urls))
    for result in results:
        print(
            f"[stdout]\n{result[0].decode().strip()}\n[stderr]\n{result[1].decode().strip()}"
        )


def fetch_all_containers():
    asyncio.run(fetch_containers(all_containers=True))


def fetch_language_containers():
    parser = argparse.ArgumentParser()
    parser.add_argument("language", help="language/container type")
    arg = parser.parse_args()
    asyncio.run(fetch_containers(container_type=arg.language))
