from __future__ import print_function

import sys
from os.path import basename

import yaml

import lib
from lib.vultr import Server
from lib.ssh2vm import SSH2VM

def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


class Provisioner:
    srv = None
    vm = None
    label = None
    ip = None

    def __init__(self, mock, label, plan=29, datacenter=9, boot=None):
        """
        plan 29 is 768 MB RAM,15 GB SSD,1.00 TB BW and can be found at https://api.vultr.com/v1/plans/list 90 is 3GB at dc 1
        data center 9 is at Frankfurt and each datacenter has specific plans. Data centers list is at https://api.vultr.com/v1/regions/list
        """
        self.label = label
        self.srv = lib.vultr.Server(mock)
        self.srv.create(label, plan, datacenter, boot)

    def destroy(self):
        self.srv.destroy()


def main(filename, mock=False):
    yml = yaml.load(open(filename).read())
    assert 'servers' in yml.keys(), yml
    servers_info = yml['servers']
    try:
        # creates all IPs as a VM might use the IP of another VM
        for server in servers_info:
            name = server['name']
            if 'boot' in server.keys() and 'script' in server['boot'].keys():
                server['provisioner'] = Provisioner(mock, name, boot=server['boot']['script'])
            else:
                server['provisioner'] = Provisioner(mock, name)

        for server in servers_info:
            server['ip'] = server['provisioner'].srv.getip()
        # checks ports of each VM
        check_ports_at(servers_info, 'boot')
        # sets env var of each VM if any, uploads script and runs it
        start(servers_info)
        # checks ports of each VM
        check_ports_at(servers_info, 'start')
    finally:
        try:
            for server in servers_info:
                if 'ip' in server.keys():
                    ssh = lib.ssh2vm.SSH2VM(server['ip'])
                    for mode in ['boot', 'start']:
                        if mode in server.keys():
                            for log in server[mode]['logs']:
                                if ssh.exists(log):
                                    ssh.execute("cat %s" % log)
        finally:
            if 'ci' in yml.keys() and yml['ci']:
                for server in servers_info:   # wait 10 minutes (until travis is about to kill the job) and then fail
                    if 'provisioner' in server.keys():
                        server['provisioner'].destroy()


def check_ports_at(servers_info, section):
    for server in servers_info:  # wait 10 minutes (until travis is about to kill the job) and then fail
        if section in server.keys() and 'ports' in server[section].keys():
            for port in server[section]['ports']:
                ssh = lib.ssh2vm.SSH2VM(server['ip'])
                assert ssh.wait_net_service(int(port), 560), "Expected port %d of %s to be up" % (port, server['ip'])


def start(servers_info):
    """
    For each server with a 'start' section
    uploads script
    sets each environment variable of 'dependencies' with the IP of a server
    executes script
    :param servers_info: updates ['start']['dependencies'].values()
    :return:
    """
    for server in servers_info:
        if 'start' in server.keys():
            if 'dependencies' in server['start'].keys():
                for dependency in server['start']['dependencies']:
                    name = server['start']['dependencies'][dependency]
                    for other_server in servers_info:
                        if other_server['name'] == name:
                            server['start']['dependencies'][dependency] = other_server['ip']
                            break
            if 'script' in server['start'].keys():
                ssh = lib.ssh2vm.SSH2VM(server['ip'])
                ssh.upload(server['start']['script'])
                filename = basename(server['start']['script'])
                if 'dependencies' in server['start'].keys():
                    ssh.execute("bash %s" % filename, server['start']['dependencies'])
                else:
                    ssh.execute("bash %s" % filename, {})


if __name__ == "__main__":
    assert len(sys.argv) > 0, "Expected exactly one argument with the input filename"
    main(sys.argv[1])
