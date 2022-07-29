#!/bin/bash
ENABLED_PORT="8926"

iptables -F &&
iptables -A OUTPUT -j ACCEPT -m state --state ESTABLISHED &&
iptables -A OUTPUT -j ACCEPT -o lo &&
iptables -P OUTPUT DROP &&
iptables -A INPUT -j ACCEPT -i lo &&
iptables -A INPUT -j ACCEPT -m state --state ESTABLISHED &&
iptables -A INPUT -p tcp --dport "$ENABLED_PORT" -j ACCEPT &&
iptables -P INPUT DROP &&
iptables -P FORWARD DROP &&
ip6tables -P FORWARD DROP &&
ip6tables -P INPUT DROP &&
ip6tables -P OUTPUT DROP || (
    echo "ERR: Failed, disabling firewall" >&2
    iptables -P INPUT ACCEPT
    iptables -P OUTPUT ACCEPT
    ip6tables -P INPUT ACCEPT
    ip6tables -P OUTPUT ACCEPT
    false
)

