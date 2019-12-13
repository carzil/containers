FROM library/ubuntu:19.04

RUN apt-get update -y
RUN apt-get install -y python3 python3-pip curl iproute2 iputils-ping htop strace iptables

WORKDIR /enki

COPY requirements.txt .
RUN pip3 install -r requirements.txt

COPY scripts ./scripts
COPY enkilib ./enkilib
COPY tests ./tests
COPY enki ./

