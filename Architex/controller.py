import yaml
import os
import crossplane
import urllib.parse
from yaml.loader import SafeLoader
from diagrams import Diagram
from diagrams.c4 import Person, Container, Database, SystemBoundary, Relationship

global_names = []


def container_name2service_name(container_name):
    for item in global_names:
        if item['container_name'] == container_name:
            return item['service_name']


def populate_composes(docker_composes, compose_files, repo_path, search):
    def get_filepaths(repo_path):
        res = []
        for (dir_path, dir_names, file_names) in os.walk(repo_path):
            for file_name in file_names:
                res.append(f'{dir_path}/{file_name}')
        return res

    filepaths = get_filepaths(repo_path) if search else repo_path
    for filepath in filepaths:
        if (".yml" in filepath or ".yaml" in filepath):
            file = open(filepath)
            loadedYaml = {}
            try:
                loadedYaml = yaml.load(file, Loader=SafeLoader)
                loadedYaml = {} if loadedYaml is None else loadedYaml
            except:
                None
            if loadedYaml.get("services"):
                docker_composes.append(loadedYaml)
                compose_files.append(filepath)
            file.close()


def service_to_container(name, service):
    withNetworks = ', '.join([x for x in service.get(
        'networks') if x != 'default']) if service.get(
        'networks') != None else None

    name = f'{service.get("container_name")} ({name})' if "container_name" in service else name
    if withNetworks:
        with SystemBoundary(f'Custom network(s) : {withNetworks}'):
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


def volume_to_database(name, access_mode, technology):
    return Database(
        name=name,
        technology=technology,
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


def populate_databases(docker_compose, databases):
    if docker_compose.get("volumes"):
        for name, volume in docker_compose["volumes"].items():
            desc_strings = []
            if volume != None:
                for key, value in volume.items():
                    desc_strings.append(f'{value} {key}')
            databases[name] = volume_to_database(
                name, 'copy', f'named volume with {", ".join(desc_strings) if len(desc_strings) else "no description"}')

    for name, service in docker_compose["services"].items():
        if "volumes" in service:
            for volume_string in service["volumes"]:
                volume_name, _, access_mode = (volume_string.split(
                    ":") + [None]*2)[:3]
                if databases.get(volume_name) == None:
                    databases[volume_name] = volume_to_database(
                        volume_name, access_mode if access_mode != None else 'rw', 'bind-mounted file system')


def populate_containers(docker_compose, containers, compose_file, repo_path):
    composeNetwork = SystemBoundary(
        f'Default network : {compose_file.replace(repo_path,"")}')
    with composeNetwork:
        for name, service in docker_compose["services"].items():
            containers[name] = service_to_container(name, service)

            global global_names
            if "nginx" in name or (service.get("image") is not None and "nginx" in service.get("image")) or (service.get("volumes") is not None and len([volume_string for volume_string in service['volumes'] if 'nginx' in volume_string])):
                path_strings = compose_file.split('/')[:-1]
                to_be_appended = [
                    volume_string for volume_string in service['volumes']if 'nginx' in volume_string and 'conf' in volume_string][0].split(':')[0]
                if (to_be_appended is None and service.get('build')):
                    to_be_appended = f'{service["build"]["context"]}/nginx.conf'
                path_strings.append(to_be_appended)
                global_names.append({'service_name': name, 'container_name':  service.get(
                    "container_name") if "container_name" in service else name, 'nginx_path': '/'.join(path_strings)})
            else:
                global_names.append({'service_name': name, 'container_name':  service.get(
                    "container_name") if "container_name" in service else name})


def get_compose_relationships(docker_compose, containers, databases, user):
    for name, service in docker_compose["services"].items():
        if "depends_on" in service:
            containers[name] >> Relationship("depends on") >> list(map(
                lambda destination_service: containers[destination_service] if containers.get(destination_service) else containers[container_name2service_name(destination_service)], service.get("depends_on")))
        if "volumes" in service:
            for volume_string in service["volumes"]:
                volume_name, container_path = (volume_string.split(
                    ":") + [None]*1)[:2]
                containers[name] >> Relationship(
                    f'mount {container_path if container_path else volume_name}') >> databases[volume_name]
        if "ports" in service:
            for port_string in service["ports"]:
                host, container = port_string.split(
                    ":")
                user >> Relationship(
                    f'access port {host}, forwarded to {container}') >> containers[name]


def get_nginx_relationships(location_blocks, containers, nginx_container_name):
    for location_block in location_blocks:
        root_blocks, proxy_blocks, fastcgi_blocks, version = [], [], [], None
        for block in location_block['block']:
            if block["directive"] == "root":
                root_blocks.append(block.get("args")[0])
            if block["directive"] == "proxy_pass":
                proxy_blocks.append(block.get("args")[0])
            if block["directive"] == "fastcgi_pass":
                fastcgi_blocks.append(block.get("args")[0])
            if block["directive"] == "proxy_http_version":
                version = block.get("args")[0]

        def pass_block_to_relationship(pass_block, is_fastcgi=False):
            target_container_name = urllib.parse.urlparse(
                pass_block).netloc.split(":")[0]
            target_container = None
            if containers.get(
                    target_container_name):
                target_container = containers[target_container_name]
            elif containers.get(container_name2service_name(target_container_name)):
                target_container = containers[container_name2service_name(
                    target_container_name)]
            else:
                target_container = Container(
                    name=target_container_name,
                    technology=target_container_name if is_fastcgi else f'proxy_http_version {version}',
                    description=pass_block,
                )
                containers[target_container_name] = target_container

            containers[nginx_container_name] >> Relationship(
                f'{location_block.get("args")[0]} {"fastcgi" if is_fastcgi else "proxy"} pass') >> target_container

        if root_blocks:
            for root_block in root_blocks:
                web = Container(
                    name="web client",
                    technology="static web",
                    description=f'{root_block} nginx service directory',
                )
                containers[nginx_container_name] >> Relationship(
                    f'{location_block.get("args")[0]} simple redirection') >> web

        elif proxy_blocks:
            for proxy_block in proxy_blocks:
                pass_block_to_relationship(proxy_block)

        elif fastcgi_blocks:
            for fastcgi_block in fastcgi_blocks:
                pass_block_to_relationship(fastcgi_block, True)


def start_drawing(repo_path, search):
    docker_composes, compose_files = [], []
    repo_path = repo_path[0] if search else repo_path
    reponame = repo_path.split(
        "/")[-1] if search and "/" in repo_path else "current"

    populate_composes(docker_composes, compose_files, repo_path, search)
    with Diagram(f'{reponame} Architectural Diagram', filename=f'{reponame}_architecture',  graph_attr={
        "splines": "spline",
    }, show=False):
        containers, databases, user = {}, {}, Person(
            name="User", description="General User")

        for index, docker_compose in enumerate(docker_composes):
            populate_databases(docker_compose, databases)
            populate_containers(docker_compose, containers,
                                compose_files[index], repo_path if search else "")
            get_compose_relationships(
                docker_compose, containers, databases, user)

        for item in global_names:
            nginx_filepath = item.get("nginx_path")
            if nginx_filepath:
                get_nginx_relationships(
                    get_location_blocks(crossplane.parse(
                        f'{os.getcwd()}/{nginx_filepath}')), containers, item.get("service_name"))
