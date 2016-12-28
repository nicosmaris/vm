from __future__ import print_function
import sys

from time import sleep
from sys import argv
from requests import post, get
from requests.auth import HTTPBasicAuth
from os import environ

from datetime import timedelta
from delorean import Delorean


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


class VultrAPI():
    """
    Using a VPS service is more stable than docker orchestration and easier to learn. Vultr seams to be the cheapest one.
    """
    def __init__(self, filename):
        """

        :param filename: of file that holds the API token
        """
        self.filename = filename
        self.url = 'https://api.vultr.com/v1'

    def vultr_post(self, endpoint, data):
        result = None
        headers = {'api_key': open(self.filename).read().strip()}
        response = post(self.url+endpoint, params=headers, data=data, timeout=60)
        try:
            json_object = response.json()
        except ValueError, e:
            result = response
        else:
            result = response.json()
        return result

    def vultr_get(self, endpoint, data):
        result = None
        data['api_key'] = open(self.filename).read().strip()
        response = get(self.url + endpoint, params=data)
        try:
            json_object = response.json()
        except ValueError, e:
            result = response
        else:
            result = response.json()
        return result


class Server:
    ip = None
    startuptime = None

    def create(self, label):
        """
        Creates a new vm at vultr. Usually it takes 2 minutes.
        :param label:
        :return: ip
        """
        v = VultrAPI('token')
        data = {
            'DCID':9,             # data center at Frankfurt
            'VPSPLANID':29,       # 768 MB RAM,15 GB SSD,1.00 TB BW
            'OSID':215,           # virtualbox running ubuntu 16.04 x64
            'label':label,        #
            'SSHKEYID':'5794ed3c1ce42' # github key
        }
        if label.startswith('test'):
            data['notify_activate'] = 'no'
        response = v.vultr_post('/server/create', data)
        self.startuptime = Delorean()
        self.id = response['SUBID']
        try:
            while True:
                if Delorean() - self.startuptime < timedelta(minutes=10):
                    srv = v.vultr_get('/server/list', {'SUBID': self.id})
                    if srv['power_status'] == 'running' and srv['main_ip'] != '0' and srv['default_password'] != '':
                        eprint("Waiting for ssh to become available and dpkg to become unlocked so that we can apt-get install")
                        sleep(10)
                        self.ip = srv['main_ip']
                        break
                    eprint("Waiting for vultr to create server")
                    sleep(10)
                else:
                    assert False, 'Failed to get status of new server within 5 minutes'
        except:
            self.destroy()
            raise
        if self.ip==None:
            raise
        return self.ip

    def destroy(self):
        while True:
            if Delorean() - self.startuptime < timedelta(minutes=5):
	        sleep(10)
            else:
                v = VultrAPI('token')
                response = v.vultr_post('/server/destroy', {'SUBID': self.id})
                assert response.status_code == 200, "Failed to destroy server with id %d" % self.id
                break

