#!/usr/bin/python
# -*- coding: utf-8 -*-

# (c) 2013, Darrel O'Pry <darrel.opry at spry-group.com>
#
# This file is part of Ansible
#
# Ansible is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Ansible is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Ansible.  If not, see <http://www.gnu.org/licenses/>.

DOCUMENTATION = '''
---
module: digital_ocean_domain_record
author: "Darrel O'Pry (@sprygroup) and James Gaspari (@pogotech)"
short_description: Create/delete a DNS record in DigitalOcean
description:
     - Create/delete a DNS record in DigitalOcean.
version_added: "2.2"
options:
  state:
    description:
     - Indicate desired state of the target.
    default: present
    choices: ['present', 'absent']
  api_token:
    description:
     - Digital Ocean api key.
  domain:
    description:
     - Required, String, Domain Name (e.g. domain.com), specifies the domain
       for which to create a record.
  type:
    description:
     - Required, String, the type of record you would like to create. A, CNAME,
       NS, TXT, MX or SRV.
  data:
    description:
     - Required, String, this is the value of the record.
  name:
    description:
     - Optional, String, required for A, CNAME, TXT and SRV records.
  priority:
    description:
     - Optional, Integer, required for SRV and MX records.
  port:
    description:
     - Optional, Integer, required for SRV records.
  weight:
    description:
     - Optional, Integer, required for SRV records.
notes:
  - Two environment variables can be used, DO_API_KEY and DO_API_TOKEN. They both refer to the v2 token.
  - As of Ansible 1.9.5 and 2.0, Version 2 of the DigitalOcean API is used, this removes C(client_id) and C(api_key) options in favor of C(api_token).
requirements:
  - "python >= 2.6"
  - dopy
'''

EXAMPLES = '''
# Create a DNS record
- digital_ocean_domain: >
      state=present
      domain=digitalocean.example
      type="A"
      name=www
      ip=127.0.0.1
# Remove a DNS record
- digital_ocean_domain: >
      state=absent
      domain=digitalocean.example
      type="A"
      name=www
      ip=127.0.0.1
# Create a droplet and a corresponding DNS record
- digital_ocean: >
      state=present
      name=test_droplet
      size_id=1
      region_id=2
      image_id=3
  register: test_droplet
- digital_ocean_domain: >
      state=present
      domain=digitalocean.example
      type="A"
      name={{ test_droplet.droplet.name }}
      data={{ test_droplet.droplet.ip_address }}
'''
RETURN = '''
data:
    description: The value of the DNS record that you are creating
    returned: success
    type: string
    sample: "192.168.1.5"
id:
    description: The Digital Ocean DNS record ID
    returned: success
    type: integer
    sample: 15547554
name:
    description: The name of the record that you are adding
    returned: success
    type: string
    sample: "gitlab"
port:
    description: Port information of a SRV record
    returned: success
    type: integer
    sample: null
priority:
    description: The priority of the SRV or MX record
    returned: success
    type: integer
    sample: null
type:
    description: The record type that is being created
    returned: success
    type: string
    sample: "A"
weight:
    description: The weight of the SRV record that is being created
    returned: success
    type: integer
    sample: null

'''

import sys
import os
import time

try:
    from dopy.manager import DoError, DoManager
    HAS_DOPY = True
except ImportError as e:
    HAS_DOPY = False


class TimeoutError(DoError):
    def __init__(self, msg, id):
        super(TimeoutError, self).__init__(msg)
        self.id = id


class JsonfyMixIn(object):
    def to_json(self):
        return self.__dict__


class DomainRecord(JsonfyMixIn):
    manager = None

    def __init__(self, json):
        self.__dict__.update(json)
    update_attr = __init__

    @classmethod
    def list_all(cls, domain):
        domain_records = cls.manager.all_domain_records(domain)
        return map(cls, domain_records)

    # @classmethod
    # def updates(cls, id, domain, type, data):
    #     record_type = type
    #     json = cls.manager.edit_domain_record(domain, id, record_type, data)
    #     return cls(json)

    @classmethod
    def destroy(cls, domain, id):
        json = cls.manager.destroy_domain_record(domain, id)
        return json

    @classmethod
    def add(cls, domain, type, data, name=None, priority=None,
                port=None, weight=None):
        json = cls.manager.new_domain_record(domain, type, data, name,
                                             priority, port, weight)
        return cls(json)

    @classmethod
    def find_record(cls, domain=None, type=None, data=None, name=None,
                    priority=None, port=None, weight=None):

        all_records = DomainRecord.list_all(domain)

        for record in all_records:
            if (record.type == type and record.data == data
                and record.name == name and record.priority == priority
                and record.port == port and record.weight == weight):
                return record

        return False

class Domain(JsonfyMixIn):
    manager = None

    def __init__(self, domain_json):
        self.__dict__.update(domain_json)

    @classmethod
    def setup(cls, api_token):
        cls.manager = DoManager(None, api_token, api_version=2)
        DomainRecord.manager = cls.manager

    @classmethod
    def list_all(cls):
        domains = cls.manager.all_domains()
        return map(cls, domains)

    # @classmethod
    # def find(cls, name=None, id=None):
    #     if name is None and id is None:
    #         return False
    #
    #     domains = Domain.list_all()
    #
    #     if id is not None:
    #         for domain in domains:
    #             if domain.id == id:
    #                 return domain
    #
    #     if name is not None:
    #         for domain in domains:
    #             if domain.name == name:
    #                 return domain
    #
    #     return False

def core(module):
    def getkeyordie(k):
        v = module.params[k]
        if v is None:
            module.fail_json(msg='Unable to load %s' % k)
        return v

    try:
        api_token = module.params['api_token'] or os.environ['DO_API_TOKEN'] or os.environ['DO_API_KEY']
    except KeyError as e:
        module.fail_json(msg='Unable to load %s' % e.message)

    type = getkeyordie("type")
    data = module.params['data']
    name = module.params['name']
    priority = module.params['priority']
    port = module.params['port']
    weight = module.params['weight']
    domain = module.params['domain']
    changed = True
    state = module.params['state']
    domain_name = getkeyordie("domain")

    Domain.setup(api_token)

    if not domain:
        module.fail_json(msg='Domain not found %s' % domain_name)

    record = DomainRecord.find_record(domain_name, type,
                data, name, priority, port, weight)

    if state in ('present') and not record:
        record = DomainRecord.add(domain_name, type, data, name, priority, port, weight)
        module.exit_json(changed=True, record=record.to_json())

    # elif state in ('present') and record:
    #     json = DomainRecord.updates(record.id, domain_name, type, data)
    #     module.exit_json(changed=True, record=record.to_json())

    elif state in ('absent') and record:
        json = DomainRecord.destroy(domain_name, record.id)
        module.exit_json(changed=True, event=json)

    module.exit_json(changed=False, record=record.to_json())


def main():
    module = AnsibleModule(
        argument_spec=dict(
            state=dict(choices=['present', 'absent'], default='present'),
            api_token=dict(aliases=['API_TOKEN'], no_log=True),
            domain=dict(type='str'),
            type=dict(choices=['A', 'AAAA', 'CNAME', 'MX', 'TXT', 'SRV', 'NS'],
                      default='A'),
            name=dict(type='str'),
            data=dict(type='str'),
            priority=dict(type='int'),
            port=dict(type='int'),
            weight=dict(type='int'),
        )
    )

    try:
        core(module)
    except TimeoutError as e:
        module.fail_json(msg=str(e), id=e.id)
    except (DoError, Exception) as e:
        module.fail_json(msg=str(e))

# import module snippets
from ansible.module_utils.basic import *

main()
