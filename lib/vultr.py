from __future__ import print_function
import sys

from time import sleep
from sys import argv
from requests import post, get
from requests.auth import HTTPBasicAuth
from os import environ

from datetime import timedelta
from delorean import Delorean
import hashlib


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
        except:
            assert False, "HTTP status code %d and response text %s" % (response.status_code, response.text)
        else:
            result = json_object
        return result


class Script:
    scriptid = None

    def create(self, filename):
        v = VultrAPI('token')
        script = open('deploy/install_docker.sh').read()
        if filename!=None:
            script += open(filename).read()
        name = hashlib.md5(script).digest().encode("base64")
        response = v.vultr_get('/startupscript/list', {})
        if isinstance(response, list):
            scripts = response
        else:
            scripts = response.values()
        for startupscript in scripts:
            if startupscript['name'] == name:
                self.scriptid = startupscript['SCRIPTID']
                break
        if self.scriptid==None:
            data = {
                'name': name,
                'script': script
            }
            response = v.vultr_post('/startupscript/create', data)
            self.scriptid = response['SCRIPTID']
        return self.scriptid

    def destroy(self):
        v = VultrAPI('token')
        data = {
            'SCRIPTID': self.scriptid
        }
        response = v.vultr_post('/startupscript/destroy', data)


class Server:
    subid = None
    ip = None
    startuptime = None
    script = Script()

    def __init__(self, mock):
        self.mock = mock

    def create(self, label, plan, datacenter, boot):
        """
        Creates a new vm at vultr. Usually it takes 2 minutes.
        :param label:
        :return: ip
        """
        self.label = label
        v = VultrAPI('token')
        scriptid = self.script.create(boot)
        data = {
            'DCID':      datacenter,             # data center at Frankfurt
            'VPSPLANID': plan,       # 768 MB RAM,15 GB SSD,1.00 TB BW
            'OSID':      215,           # virtualbox running ubuntu 16.04 x64
            'label':     label,        #
            'SSHKEYID':  '5794ed3c1ce42',
            'SCRIPTID':  scriptid       # at digitalocean this is called user_data and the format of the value is cloud-config
        }
        if label.startswith('test'):
            data['notify_activate'] = 'no'
        response = v.vultr_post('/server/create', data)
        self.startuptime = Delorean()
        if hasattr(response, 'text') and 'reached the maximum number of active virtual machines' in response.text:
            assert False, response.text
        self.subid = response['SUBID']

    def getip(self):
        v = VultrAPI('token')
        try:
            while True:
                if Delorean() - self.startuptime < timedelta(minutes=10):
                    srv = v.vultr_get('/server/list', {'SUBID': self.subid})
                    if srv['power_status'] == 'running' and srv['main_ip'] != '0' and srv['default_password'] != '':
                        self.ip = srv['main_ip']
                        break
                    eprint("Waiting for vultr to create " + self.label)
                    sleep(10)
                else:
                    assert False, "Failed to get status of new %s within 5 minutes" % self.label
        except:
            self.destroy()
            raise
        if self.ip==None:
            raise
        return self.ip

    def destroy(self):
        while True:
            if self.mock or not (Delorean() - self.startuptime < timedelta(minutes=5)):
                eprint(self.ip)
                eprint("1...")
                v = VultrAPI('token')
                eprint("2...")
                response = v.vultr_post('/server/destroy', {'SUBID': self.subid})
                eprint("3...")
                self.script.destroy()
                eprint("4...")
                break
            else:
                eprint("Waiting 5 minutes for vultr to allow destroying a fresh vm...")
                sleep(10)


