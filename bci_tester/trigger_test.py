from dataclasses import dataclass, field
import json
from logging import getLogger
from os import environ
from typing import (
    Dict,
    Literal,
    List,
    Optional,
    NoReturn,
    Tuple,
    TypedDict,
    Union,
)

import pika
import requests

from bci_tester.parse_data import containers, Container


LOGGER = getLogger(__name__)
GITHUB_API_BASEURL = "https://api.github.com"


class PublishBodyBase(TypedDict):
    #: name of the project which' publishing state changed
    project: str
    #: repository which' publishing state changed
    repo: str


class PacktrackBody(PublishBodyBase):
    #: some id identifying something
    payload: str


class PublishStateBody(PublishBodyBase):
    #: the new state of the project + repository
    state: Literal[
        "unknown",
        "broken",
        "scheduling",
        "blocked",
        "building",
        "finished",
        "publishing",
        "published",
        "unpublished",
    ]


class PublishedBody(PublishBodyBase):
    #: some internal (=undocumented) build ID
    buildid: str


def trigger_workflow(
    event_type: str = "containers_published",
    owner: str = "SUSE",
    repo: str = "BCI-tests",
):
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "Authorization": f"token {environ['GITHUB_TOKEN']}",
    }

    try:
        resp = requests.post(
            f"{GITHUB_API_BASEURL}/repos/{owner}/{repo}/dispatches",
            json={"event_type": event_type},
            headers=headers,
        )

        if resp.status_code != 204:
            LOGGER.error("triggering the workflow failed with %s", resp.status)
    except Exception as exc:
        LOGGER.error("sending the workflow trigger failed with %s", exc)


@dataclass
class RabbitMQConnection:
    #: url to the message bus, defaults to openSUSE's
    url: str = "amqps://opensuse:opensuse@rabbit.opensuse.org"
    #: the rabbitMQ prefix used by OBS, see
    #: https://openbuildservice.org/help/manuals/obs-admin-guide/obs.cha.administration.html#_message_bus
    message_topic_prefix: str = "opensuse.obs"

    #: list of routing keys corresponding to the repository publishing events
    repository_routing_keys: List[str] = field(default_factory=list)

    #: Dictionary of project names (as keys) mapping to a list of repositories
    #: whose publishing event triggers a CI run on github
    watched_projects: Dict[str, List[str]] = field(default_factory=dict)

    container_list: Optional[List[Container]] = None

    def __post_init__(self):
        if self.container_list is None:
            self.container_list = containers

        self.repository_routing_keys = [
            f"{self.message_topic_prefix}.repo.publish_state",
            f"{self.message_topic_prefix}.repo.published",
        ]

        for container in self.container_list:
            repo_entries = container.repo.split("/")
            project = ":".join(repo_entries[:-1])
            repository = repo_entries[-1]
            if (
                project in self.watched_projects
                and repository not in self.watched_projects[project]
            ):
                self.watched_projects[project].append(repository)
            elif project not in self.watched_projects:
                self.watched_projects[project] = [repository]

    def connect_channel_to_bus(self) -> Tuple[pika.channel.Channel, str]:
        connection = pika.BlockingConnection(
            pika.URLParameters("amqps://opensuse:opensuse@rabbit.opensuse.org")
        )
        channel = connection.channel()

        channel.exchange_declare(
            exchange="pubsub",
            exchange_type="topic",
            passive=True,
            durable=True,
        )

        result = channel.queue_declare("", exclusive=True)
        queue_name = result.method.queue

        channel.queue_bind(
            exchange="pubsub", queue=queue_name, routing_key="#"
        )
        return channel, queue_name

    def get_callback(self):
        def callback(ch, method, properties, body):
            if method.routing_key in self.repository_routing_keys:
                try:
                    payload: Union[
                        PublishStateBody, PublishedBody
                    ] = json.loads(body)
                except json.decoder.JSONDecodeError:
                    return

                if (
                    payload is None
                    or payload["project"] not in self.watched_projects
                ):
                    return

                if (
                    payload["repo"]
                    in self.watched_projects[payload["project"]]
                ):
                    trigger_workflow()

        return callback


def trigger_from_mqtt(connection: RabbitMQConnection() = None) -> NoReturn:
    if not environ.get("GITHUB_TOKEN"):
        raise RuntimeError("environment variable GITHUB_TOKEN not set")

    if connection is None:
        connection = RabbitMQConnection()

    channel, queue_name = connection.connect_channel_to_bus()

    channel.basic_consume(queue_name, connection.get_callback(), auto_ack=True)
    channel.start_consuming()
