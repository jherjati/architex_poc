import yaml
import os
import sys
import crossplane
import urllib.parse
from yaml.loader import SafeLoader
from diagrams import Diagram
from diagrams.c4 import Person, Container, Database, SystemBoundary, Relationship


def container_name2service_name(container_name):
    for item in names:
        if item['container_name'] == container_name:
            return item['service_name']


def get_compose_files(dir_path):
    res = []
    for path in os.listdir(dir_path):
        if os.path.isfile(os.path.join(dir_path, path)):
            res.append(path)
    return res


def service_to_container(name, service):
    withNetworks = ', '.join([x for x in service.get(
        'networks') if x != 'default']) if service.get(
        'networks') != None else None

    name = service.get(
        "container_name") if "container_name" in service else name
    if withNetworks:
        with SystemBoundary(f'{withNetworks} custom network'):
            return Container(
                name=name,
                technology=service.get(
                    "image") if "image" in service else f'Built on {service["build"] if isinstance(service["build"], str) else service["build"]["context"]} folder',
                description=service.get("restart"),
            )
    else:
        return Container(
            name=name,
            technology=service.get(
                "image") if "image" in service else f'Built on {service["build"] if isinstance(service["build"], str) else service["build"]["context"]} folder',
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


def nginx_detection(docker_compose):
    for name, service in docker_compose["services"].items():
        global names
        names.append({'service_name': name, 'container_name':  service.get(
            "container_name") if "container_name" in service else name})
        if "nginx" in name or (service.get("image") is not None and "nginx" in service.get("image")):
            global nginx_service_name
            nginx_service_name = name
            global user
            user = Person(
                name="User", description="General User"
            )


def populate_databases(docker_compose, databases):
    for name, service in docker_compose["services"].items():
        if "volumes" in service:
            for volume_string in service["volumes"]:
                volume, container_path, access_mode = (volume_string.split(
                    ":") + [None]*3)[:3]
                databases[volume] = volume_to_database(volume, access_mode)


def populate_containers(docker_compose, containers, compose_file):
    composeNetwork = SystemBoundary(f'{compose_file} default network')
    with composeNetwork:
        for name, service in docker_compose["services"].items():
            containers[name] = service_to_container(name, service)


def get_compose_relationships(docker_compose, containers, databases):
    for name, service in docker_compose["services"].items():
        if "depends_on" in service:
            containers[name] >> Relationship("depends on") >> list(map(
                lambda destination_service: containers[destination_service] if containers.get(destination_service) else containers[container_name2service_name(destination_service)], service.get("depends_on")))
        if "volumes" in service:
            for volume_string in service["volumes"]:
                volume, container_path = (volume_string.split(
                    ":"))[:2]
                containers[name] >> Relationship(
                    f'bind mount {container_path}') >> databases[volume]
        if "ports" in service:
            for port_string in service["ports"]:
                host, container = port_string.split(
                    ":")
                user >> Relationship(
                    f'access port {host}, forwarded to {container}') >> containers[name]


def get_nginx_relationships(location_blocks, containers):
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
                f'{location_block.get("args")[0]} proxy pass') >> containers[destination_service] if containers.get(destination_service) else containers[container_name2service_name(destination_service)]
        elif fastcgi_blocks:
            destination_service = urllib.parse.urlparse(
                fastcgi_blocks[0]).netloc.split(":")[0]
            containers[nginx_service_name] >> Relationship(
                f'{location_block.get("args")[0]} fastcgi pass') >> containers[destination_service] if containers.get(destination_service) else containers[container_name2service_name(destination_service)]


def compose_drawing(docker_compose, databases, containers, compose_file):
    populate_databases(docker_compose, databases)
    populate_containers(docker_compose, containers, compose_file)
    get_compose_relationships(docker_compose, containers, databases)


graph_attr = {
    "splines": "spline",
}
repo_path = f'repos/{sys.argv[1]}'
nginx_service_name = ""
user = None
names = []


def start_drawing(filenames):
    docker_composes = []
    compose_files = []
    nginx_files = []

    for filename in filenames:
        if ('.yml' in filename or '.yaml' in filename):
            file = open(repo_path+f'/{filename}')
            docker_composes.append(yaml.load(file, Loader=SafeLoader))
            compose_files.append(filename)
            file.close()
        if ('.conf' in filename):
            nginx_files.append(filename)

    location_blocks = get_location_blocks(crossplane.parse(
        f'{os.getcwd()}/{repo_path}/{nginx_files[0]}'))

    with Diagram(f'{sys.argv[1]} Architectural Diagram', filename=f'{sys.argv[1]}_architecture',  graph_attr=graph_attr, show=False):
        containers, databases = {}, {}

        for docker_compose in docker_composes:
            nginx_detection(docker_compose)
        for index, docker_compose in enumerate(docker_composes):
            compose_drawing(docker_compose, databases,
                            containers, compose_files[index])
        get_nginx_relationships(
            location_blocks, containers)


start_drawing(get_compose_files(repo_path))
