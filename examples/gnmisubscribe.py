""" Example gnmisubscribe invocation
"""

from iosxr_grpc.cisco_grpc_client import CiscoGRPCClient
import json


def print_connectivity(connectivity):
    print connectivity


# Change client details to match your environment.

creds = open('ems.pem').read()
options = 'ems.cisco.com'
client = CiscoGRPCClient('19.83.1.0', 57400, 10, 'root', 'lab', creds, options)

paths=["openconfig-interfaces:interfaces/interface/openconfig-if-ethernet:ethernet",
	"Cisco-IOS-XR-pfi-im-cmd-oper:interfaces/interface-briefs/interface-brief"]

for x in client.gnmisubscribe(subs=paths, interval_seconds=2):
	print x
