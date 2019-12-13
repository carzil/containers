import sys
import click
from enkilib.watcher import *
from enkilib.utils import parse_memory, parse_cores


@click.group()
@click.pass_context
def cli(ctx):
    ensure_env()


@cli.command("init")
@click.argument("path")
def init(path):
    create_container(path)


@cli.command("ps")
@click.option("--all", "-a", is_flag=True)
def ps(all):
    list_containers(only_active=not all)


@cli.command("commit")
@click.argument("container_id")
def commit(container_id):
    commit_container(container_id)


@cli.command("run")
@click.argument("image")
@click.argument("command")
@click.argument("args", nargs=-1)
@click.option("--detach", "-d", is_flag=True)
@click.option("--memory-limit", "-m")
@click.option("--cpu-limit", "-c")
def run(image, command, args, detach, memory_limit, cpu_limit):
    start_container(
        image,
        command,
        args,
        detach,
        parse_memory(memory_limit),
        parse_cores(cpu_limit)
    )


@cli.command("exec")
@click.argument("container_id")
@click.argument("command")
@click.argument("args", nargs=-1)
@click.option("--detach", "-d", is_flag=True)
def exec(container_id, command, args, detach):
    exec_into_container(container_id, command, args, detach)


@cli.command("pull")
@click.argument("docker_image")
def pull(docker_image):
    pull_docker_image(docker_image)


@cli.command("rmi")
@click.argument("image_id")
def rmi(image_id):
    remove_image(image_id)


@cli.command("images")
def rmi():
    list_images()


@cli.command("logs")
@click.argument("container_id")
def logs(container_id):
    container_logs(container_id)
