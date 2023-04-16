from diagrams import Diagram
from diagrams.c4 import Person, Container, Database, SystemBoundary, Relationship

graph_attr = {
    "splines": "spline",
}

with Diagram("Geodashboard Architecture",  graph_attr=graph_attr, ):
    user = Person(
        name="User", description="General User"
    )
    redis_volumes = [Database(
        name="./redis/redis.conf",
        technology="file system",
        description="read only",
    )]

    nginx_volumes = [Database(
        name="./nginx/nginx.conf",
        technology="file system",
        description="read only",
    ), Database(
        name="./nginx/html",
        technology="file system",
        description="read only",
    )]

    with SystemBoundary("Root compose"):
        redis = Container(
            name="redis",
            technology="redis:6-alpine",
            description="always restart unless stopped",
        )

        rabbitmq = Container(
            name="rabbitmq",
            technology="rabbitmq:3-alpine",
            description="always restart unless stopped",
        )

        worker = Container(
            name="worker",
            technology="custom build on worker folder",
            description="always restart unless stopped",
        )

        directus = Container(
            name="directus",
            technology="custom build on directus folder",
            description="always restart unless stopped",
        )

        nginx = Container(
            name="nginx",
            technology="nginx:1-alpine",
            description="always restart unless stopped",
        )

        web = Container(
            name="web",
            technology="static web",
            description="always restart unless stopped",
        )

    user >> Relationship("access port 80") >> nginx
    nginx >> Relationship("/panel and /panel/files redirection") >> directus
    nginx >> Relationship("/ redirection") >> web
    directus >> Relationship("depends on") >> [redis, rabbitmq, worker]
    worker >> Relationship("depends on") >> rabbitmq
    redis >> Relationship(
        "bind mount /usr/local/etc/redis/redis.conf") >> redis_volumes[0]
    nginx >> Relationship(
        "bind mount /etc/nginx/nginx.conf") >> nginx_volumes[0]
    nginx >> Relationship("bind mount /var/www/html") >> nginx_volumes[1]
