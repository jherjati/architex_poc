import yaml
from yaml.loader import SafeLoader
from diagrams import Diagram
from diagrams.c4 import Person, Container, Database, SystemBoundary, Relationship


graph_attr = {
    "splines": "spline",
}


def service2container(name, service):
    return Container(
        name=service.get(
            "container_name") if "container_name" in service else name,
        technology=service.get(
            "image") if "image" in service else f'Built on {service["build"]["context"]} folder',
        description=service.get("restart"),
    )


def volume2database(volume, access_mode):
    return Database(
        name=volume,
        technology="file system",
        description=f'access mode : {access_mode}',
    )


with open("compose.yaml") as f:
    data = yaml.load(f, Loader=SafeLoader)
    with Diagram("Software",  graph_attr=graph_attr, show=True):
        containers, volumes, networks = {}, {}, {}
        with SystemBoundary("Default Compose Network"):
            # Container and Database initiation
            for name, service in data["services"].items():
                containers[name] = service2container(name, service)
                if "volumes" in service:
                    for volume_string in service["volumes"]:
                        volume, container_path, access_mode = volume_string.split(
                            ":")
                        volumes[volume] = volume2database(volume, access_mode)

            # Relation identification
            for name, service in data["services"].items():
                if "depends_on" in service:
                    containers[name] >> Relationship("depends on") >> list(map(
                        lambda n: containers[n], service.get("depends_on")))
                if "volumes" in service:
                    for volume_string in service["volumes"]:
                        volume, container_path, access_mode = volume_string.split(
                            ":")
                        containers[name] >> Relationship(
                            f'bind mount {container_path}') >> volumes[volume]
