import os
import signal
import uuid
import shutil
import requests
import tarfile
import sys
from pathlib import Path
from enkilib.utils import *
from enkilib.container import Container, ContainerLimits


DATA_DIR = Path("/var/lib/enki")
IMAGES_DIR = DATA_DIR / "images"
CONTAINERS_DIR = DATA_DIR / "containers"


def ensure_env():
    os.makedirs(CONTAINERS_DIR, exist_ok=True)


def create_container(init_dir):
    init_dir = os.path.abspath(init_dir)
    if not os.path.exists(init_dir):
        print("No such directory:", init_dir)
        exit(1)

    image_id = str(uuid.uuid4())
    image_dir = IMAGES_DIR / image_id
    try:
        shutil.copytree(
            src=init_dir,
            dst=image_dir / "data",
            symlinks=True,
        )
    except:
        pass

    with open(image_dir / "parent", "w") as f:
        print("none", file=f)

    print(image_id)


def start_container(image, command, args, detach, memory_limit, cpu_limit):
    container = Container.create(image)

    cfs_quota = int(cpu_limit * 100000) if cpu_limit is not None else None
    limits = ContainerLimits(
        memory=memory_limit,
        cfs_period=100000,
        cfs_quota=cfs_quota,
    )

    exit_status = container.run(image, command, args, detach, limits)
    if detach:
        print(container.id)
    else:
        exit(exit_status)


def exec_into_container(container_id, command, args, detach):
    container = Container(id=container_id)
    container.exec(command, args, detach)


def pull_docker_image(docker_image):
    splitted = docker_image.split(":")
    image = splitted[0]
    if len(splitted) == 2:
        tag = splitted[1]
    else:
        tag = "latest"

    token = requests.get("https://auth.docker.io/token?service=registry.docker.io&scope=repository:{}:pull".format(image)).json()["token"]

    headers = {
        "Authorization": "Bearer {}".format(token),
    }

    fs_layers = requests.get("https://registry-1.docker.io/v2/{}/manifests/{}".format(image, tag), headers=headers).json()["fsLayers"]

    curr = "none"
    for layer in fs_layers[1:]:
        blob_sum = layer["blobSum"]
        resp = requests.get("https://registry-1.docker.io/v2/{}/blobs/{}".format(image, blob_sum), headers=headers, stream=True)
        blob_size = int(resp.headers.get("Content-Length"))

        new_image_id = str(uuid.uuid4())
        new_image_dir = IMAGES_DIR / new_image_id
        os.makedirs(new_image_dir)
        blob_path = new_image_dir / "blob"

        with open(blob_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=4096):
                f.write(chunk)

        try:
            tar = tarfile.open(blob_path)
            data_dir = new_image_dir / "data"
            os.makedirs(data_dir)
            tar.extractall(data_dir)
        finally:
            os.unlink(new_image_dir / "blob")

        with open(new_image_dir / "parent", "w") as f:
            print(curr, file=f)

        curr = new_image_id

    print(curr)


def commit_container(cid):
    container_dir = CONTAINERS_DIR / cid
    if not container_dir.exists():
        print("No such container:", cid)
        exit(1)

    container_image_dir = container_dir / "image"

    new_image = str(uuid.uuid4())
    new_image_dir = IMAGES_DIR / new_image

    try:
        shutil.copytree(
            src=container_image_dir,
            dst=new_image_dir / "data",
            symlinks=True,
        )
    except:
        pass

    with open(container_dir / "image_id") as f:
        parent_image_id = f.read().strip()

    with open(new_image_dir / "parent", "w") as f:
        print(parent_image_id, file=f)

    print(new_image)


def list_containers(only_active):
    for container in Container.get_all():
        if only_active and not container.active():
            continue
        print(container.id)


def remove_image(image_id):
    try:
        shutil.rmtree(IMAGES_DIR / image_id)
    except:
        pass


def list_images():
    for image_id in os.listdir(IMAGES_DIR):
        print(image_id)


def container_logs(container_id):
    container = Container(container_id)
    with container.logs_file() as f:
        shutil.copyfileobj(f, sys.stdout.buffer)
