from __future__ import print_function
import sys
from lib.vultr import Server
from lib.ssh2vm import SSH2VM

from requests import post, get
from time import sleep
import socket
from errno import *
from time import time as now
import yaml
import glob
from os.path import basename


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def wait_net_service(server, port, timeout=None):
    """ Wait for network service to appear
        @param timeout: in seconds
        @return: True of False, if timeout is None may return only True or
                 throw unhandled network exception
    """
    s = socket.socket()
    # time module is needed to calc timeout shared between two exceptions
    end = now() + timeout

    while True:
        eprint("trying to connect to %s at port %d" % (server, port))
        try:
            next_timeout = end - now()  # connect might not respect our timeout so we try again until reaching it
            if next_timeout < 0:
                return False
            else:
                s.settimeout(next_timeout)
            s.connect((server, port))

        except socket.timeout, err:
            return False
        except socket.error, err:
            codes = [ETIMEDOUT, ECONNABORTED, ECONNREFUSED]
            if err[0] not in codes:
                assert False, err
            else:
                eprint("waiting 10 seconds for %s to open port %d" % (server, port))
                sleep(10)
        else:
            
            s.close()
            return True

class Provisioner:
    srv = None
    vm = None
    label = None
    ip = None

    def __init__(self, label, plan=29, datacenter=9, boot=None):
        """
        plan 29 is 768 MB RAM,15 GB SSD,1.00 TB BW and can be found at https://api.vultr.com/v1/plans/list 90 is 3GB at dc 1
        data center 9 is at Frankfurt and each datacenter has specific plans. Data centers list is at https://api.vultr.com/v1/regions/list
        """
        self.label = label
        self.srv = Server()
        self.srv.create(label, plan, datacenter, boot)

    def destroy(self):
        self.srv.destroy()


def main():
    yml = yaml.load(open('input.yml').read())
    assert 'servers' in yml.keys(), yml
    servers_info = yml['servers']
    try:
        # creates all IPs as a VM might use the IP of another VM
        for server in servers_info:
            name = server['name']
            if 'script' in server['boot'].keys():
                server['provisioner'] = Provisioner(name, boot=server['boot']['script'])
            else:
                server['provisioner'] = Provisioner(name)

        for server in servers_info:
            server['ip'] = server['provisioner'].srv.getip()
        # checks ports of each VM
        for server in servers_info:   # wait 10 minutes (until travis is about to kill the job) and then fail
            for port in server['boot']['ports']:
                ip = server['ip']
                assert wait_net_service(ip, port, 560), "Expected port %d of %s to be up" % (port, ip)
        # sets env var of each VM if any, uploads script and runs it
        for server in servers_info:  # wait 10 minutes (until travis is about to kill the job) and then fail
            if 'start' in server.keys():
                if 'dependencies' in server.keys():
                    for dependency in server['dependencies']:
                        name = server['dependencies'][dependency]
                        for other_server in servers_info:
                            if other_server['name'] == name:
                                server['dependencies'][dependency] = other_server['ip']
                if 'script' in server['start'].keys():
                    ssh = SSH2VM(server['ip'])
                    ssh.upload(server['start']['script'])
                    filename = basename(server['start']['script'])
                    if 'dependencies' in server.keys():
                        ssh.execute("bash %s" % filename, server['dependencies'])
                    else:
                        ssh.execute("bash %s" % filename)
        # checks ports of each VM
        for server in servers_info:  # wait 10 minutes (until travis is about to kill the job) and then fail
            if 'start' in server.keys():
                for port in server['start']['ports']:
                    ip = server['ip']
                    assert wait_net_service(ip, port, 560), "Expected port %d of %s to be up" % (port, ip)
    finally:
        if 'ci' in servers_info.keys() and servers_info['ci']:
            for server in servers_info:   # wait 10 minutes (until travis is about to kill the job) and then fail
                if 'provisioner' in server.keys():
                    server['provisioner'].destroy()


if __name__ == "__main__":
    main()
