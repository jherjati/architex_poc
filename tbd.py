import yaml
import os
import crossplane
import urllib.parse
from yaml.loader import SafeLoader
from diagrams import Diagram
from diagrams.c4 import Person, Container, Database, SystemBoundary, Relationship


graph_attr = {
    "splines": "spline",
}


def service_to_container(name, service):
    return Container(
        name=service.get(
            "container_name") if "container_name" in service else name,
        technology=service.get(
            "image") if "image" in service else f'Built on {service["build"]["context"]} folder',
        description=service.get("restart"),
    )


def volume_to_database(volume, access_mode):
    return Database(
        name=volume,
        technology="file system",
        description=f'access mode : {access_mode}',
    )


def get_location_blocks(nginx_conf):
    http_blocks = [block for block in nginx_conf.get(
        "config")[0].get("parsed") if block["directive"] == "http"]

    server_blocks, location_blocks = [], []
    for http_block in http_blocks:
        blocks = list(filter(
            lambda block: block["directive"] == "server", http_block['block']))
        server_blocks.extend(blocks)
    for server_block in server_blocks:
        blocks = list(filter(
            lambda block: block["directive"] == "location", server_block['block']))
        location_blocks.extend(blocks)

    return location_blocks


with open("compose.yaml") as f:
    docker_compose = yaml.load(f, Loader=SafeLoader)
    location_blocks = get_location_blocks(crossplane.parse(
        f'{os.getcwd()}/nginx.conf'))
    nginx_service_name = ""

    with Diagram("Software",  graph_attr=graph_attr, show=False):
        containers, databases, networks = {}, {}, {}

        # Database initiation and nginx service detection
        for name, service in docker_compose["services"].items():
            if "volumes" in service:
                for volume_string in service["volumes"]:
                    volume, container_path, access_mode = volume_string.split(
                        ":")
                    databases[volume] = volume_to_database(volume, access_mode)
            if "nginx" in name or (service.get("image") is not None and "nginx" in service.get("image")):
                nginx_service_name = name

        if nginx_service_name != "":
            user = Person(
                name="User", description="General User"
            )

        with SystemBoundary("Default Compose Network"):
            # Container initiation
            for name, service in docker_compose["services"].items():
                containers[name] = service_to_container(name, service)

        # RELATION IDENTIFICATION
        # Compose based relationship
        for name, service in docker_compose["services"].items():
            if "depends_on" in service:
                containers[name] >> Relationship("depends on") >> list(map(
                    lambda n: containers[n], service.get("depends_on")))
            if "volumes" in service:
                for volume_string in service["volumes"]:
                    volume, container_path, access_mode = volume_string.split(
                        ":")
                    containers[name] >> Relationship(
                        f'bind mount {container_path}') >> databases[volume]
            if "ports" in service:
                for port_string in service["ports"]:
                    host, container = port_string.split(
                        ":")
                    user >> Relationship(
                        f'access port {host}, forwarded to {container}') >> containers[name]

        # Nginx based relationship
        for location_block in location_blocks:
            root_blocks = [block.get("args")[0] for block in location_block['block']
                           if block["directive"] == "root"]
            proxy_blocks = [block.get("args")[0] for block in location_block['block']
                            if block["directive"] == "proxy_pass"]
            fastcgi_blocks = [block.get("args")[0] for block in location_block['block']
                              if block["directive"] == "fastcgi_pass"]
            if root_blocks:
                web = Container(
                    name="web",
                    technology="static web",
                    description=f'{root_blocks[0]} nginx service directory',
                )
                containers[nginx_service_name] >> Relationship(
                    f'{location_block.get("args")[0]} simple redirection') >> web
            elif proxy_blocks:
                destination_service = urllib.parse.urlparse(
                    proxy_blocks[0]).netloc.split(":")[0]
                containers[nginx_service_name] >> Relationship(
                    f'{location_block.get("args")[0]} proxy pass') >> containers[destination_service]
            elif fastcgi_blocks:
                destination_service = urllib.parse.urlparse(
                    fastcgi_blocks[0]).netloc.split(":")[0]
                containers[nginx_service_name] >> Relationship(
                    f'{location_block.get("args")[0]} fastcgi pass') >> containers[destination_service]
