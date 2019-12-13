#!/bin/bash

ip link add enki0 type bridge
ip addr add 172.16.0.1/16 dev enki0
ip link set enki0 up

iptables -t nat -A POSTROUTING -o enki0 -j MASQUERADE
iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
