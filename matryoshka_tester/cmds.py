import argparse
import asyncio


from matryoshka_tester.parse_data import containers, CONTAINER_REGISTRY
from matryoshka_tester.helpers import get_selected_runtime


from prettytable import PrettyTable


# Do real stuff
async def pull_container(url):
    """Pulls the container given in url with docker CLI"""
    runtime = get_selected_runtime()
    process = await asyncio.create_subprocess_shell(
        f"{runtime.runner_binary} pull {url}",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    return await process.communicate()


# CLI
def list_containers():
    pt = PrettyTable()
    pt.field_names = ["Language", "Version", "URL"]
    pt.align = "l"
    for container in containers:
        # TODO: Make url easier
        pt.add_row(
            [
                container.type,
                container.version,
                "/".join([CONTAINER_REGISTRY, container.repo, container.image])
                + ":"
                + container.tag,
            ]
        )
    print(pt)


async def fetch_containers(all_containers=False, container_type=""):
    # TODO: Change json decoder to have a container type, for which we can have a method to produce the url.
    containers_urls = [
        "/".join([CONTAINER_REGISTRY, container.repo, container.image])
        + ":"
        + container.tag
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
