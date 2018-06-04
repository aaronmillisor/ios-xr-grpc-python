#!bin/env
# Copyright 2016 Cisco Systems All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met:
#
#     * Redistributions of source code must retain the above copyright
# notice, this list of conditions and the following disclaimer.
#
# The contents of this file are licensed under the Apache License, Version 2.0
# (the "License"); you may not use this file except in compliance with the
# License. You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations under
# the License.

""" Libraries to connect XR gRPC server """

import grpc
from . import ems_grpc_pb2
from . import json_format
from . import ems_grpc_pb2
from . import telemetry_pb2
from . import gnmi_pb2
from . import gnmi_pb2_grpc

#from grpc.beta import implementations

class CiscoGRPCClient(object):
    """This class creates grpc calls using python.
    """
    def __init__(self, host, port, timeout, user, password, creds=None, options=None):
        """:param user: Username for device login
            :param password: Password for device login
            :param host: The ip address for the device
            :param port: The port for the device
            :param timeout: how long before the rpc call timesout
            :param creds: Input of the pem file
            :param options: TLS server name
            :type password: str
            :type user: str
            :type host: str
            :type port: int
            :type timeout:int
            :type creds: str
            :type options: str
        """

        if creds != None:
            self._target = '%s:%d' % (host, port)
            self._creds = grpc.ssl_channel_credentials(creds)
            self._options = options
            self._channel = grpc.secure_channel(
                self._target, self._creds, (('grpc.ssl_target_name_override', self._options,),))
            #self._channel = grpc.Channel(channel)
        else:
            self._host = host
            self._port = port
            self._channel = grpc.insecure_channel(self._host, self._port)
        self._stub = ems_grpc_pb2.gRPCConfigOperStub(self._channel)
        self._timeout = float(timeout)
        self._metadata = [('username', user), ('password', password)]

    def __repr__(self):
        return '%s(Host = %s, Port = %s, User = %s, Password = %s, Timeout = %s)' % (
            self.__class__.__name__,
            self._host,
            self._port,
            self._metadata[0][1],
            self._metadata[1][1],
            self._timeout
        )

    def getgnmicapability(self):
        message = gnmi_pb2.CapabilityRequest()
        gnmistub = gnmi_pb2_grpc.gNMIStub(self._channel)
        responses = gnmistub.Capabilities(message, metadata=self._metadata)
        return responses

    def gnmisubscribe(self, subs, interval_seconds):
	subscriptions = []
	interval = interval_seconds * 1000000000 # convert to ns
	for sub in subs:
		pathelems = []
		for pathlevel in sub.split("/"):
			pathelems.append(gnmi_pb2.PathElem(name=pathlevel))
		path = gnmi_pb2.Path(elem=pathelems)
		subscriptions.append(gnmi_pb2.Subscription(path=path, sample_interval=interval, mode="SAMPLE"))


	sublist = gnmi_pb2.SubscriptionList(subscription=subscriptions,encoding=2)
	subreq = [gnmi_pb2.SubscribeRequest(subscribe=sublist)]
        gnmistub = gnmi_pb2_grpc.gNMIStub(self._channel)
	stream = gnmistub.Subscribe(subreq,metadata=self._metadata)
	for unit in stream:
		yield unit



    def getconfig(self, path):
        """Get grpc call
            :param data: JSON
            :type data: str
            :return: Return the response object
            :rtype: Response stream object
        """
        message = ems_grpc_pb2.ConfigGetArgs(yangpathjson=path)
        responses = self._stub.GetConfig(message, self._timeout, metadata=self._metadata)
        objects, err = '', ''
        for response in responses:
            objects += response.yangjson
            err += response.errors
        return err, objects

    def getsubscription(self, sub_id, unmarshal=True):
        """Telemetry subscription function
            :param sub_id: Subscription ID
            :type: string
            :return: Returns discrete values emitted by telemetry stream
            :rtype: JSON formatted string
        """
        sub_args = ems_grpc_pb2.CreateSubsArgs(ReqId=1, encode=3, subidstr=sub_id)
        stream = self._stub.CreateSubs(sub_args, timeout=self._timeout, metadata=self._metadata)
        for segment in stream:
            if not unmarshal:
                yield segment
            else:
                # Go straight for telemetry data
                telemetry_pb = telemetry_pb2.Telemetry()
                telemetry_pb.ParseFromString(segment.data)
                # Return in JSON format instead of protobuf.
                yield json_format.MessageToJson(telemetry_pb)

    def flattencisco(self, telemetry_segment):
        telemetry_pb = telemetry_pb2.Telemetry()
        telemetry_pb.ParseFromString(telemetry_segment.data)

	def evenflatter(fields, basepath):
		listname = ""
		for rfield in fields:
			if not rfield.fields:
				print basepath + "/" + rfield.name
			else:
				if rfield.name=="keys" or rfield.name=="content":
					listname = ""
					evenflatter(rfield.fields, basepath + listname)
				else:
					listname = "/" + rfield.name
					evenflatter(rfield.fields, basepath + listname)

	#print telemetry_pb
	for teldata in telemetry_pb.data_gpbkv:
		print teldata.fields
		evenflatter(teldata.fields, telemetry_pb.encoding_path)
#		if teldata.fields is not None:
#			print teldata.name
#			for x in teldata.fields:
#				print x.name



    def connectivityhandler(self, callback):
        """Passing of a callback to monitor connectivety state updates.
        :param callback: A callback for monitoring
        :type: function
        """
        self._channel.subscribe(callback, True)

    def mergeconfig(self, yangjson):
        """Merge grpc call equivalent  of PATCH RESTconf call
            :param data: JSON
            :type data: str
            :return: Return the response object
            :rtype: Response object
        """
        message = ems_grpc_pb2.ConfigArgs(yangjson=yangjson)
        response = self._stub.MergeConfig(message, self._timeout, metadata=self._metadata)
        return response

    def deleteconfig(self, yangjson):
        """delete grpc call
            :param data: JSON
            :type data: str
            :return: Return the response object
            :rtype: Response object
        """
        message = ems_grpc_pb2.ConfigArgs(yangjson=yangjson)
        response = self._stub.DeleteConfig(message, self._timeout, metadata=self._metadata)
        return response

    def replaceconfig(self, yangjson):
        """Replace grpc call equivalent of PUT in restconf
            :param data: JSON
            :type data: str
            :return: Return the response object
            :rtype: Response object
        """
        message = ems_grpc_pb2.ConfigArgs(yangjson=yangjson)
        response = self._stub.ReplaceConfig(message, self._timeout, metadata=self._metadata)
        return response
    def getoper(self, path):
        """ Get Oper call
            :param data: JSON
            :type data: str
            :return: Return the response object
            :rtype: Response stream object
        """
        message = ems_grpc_pb2.GetOperArgs(yangpathjson=path)
        responses = self._stub.GetOper(message, self._timeout, metadata=self._metadata)
        objects, err = '', ''
        for response in responses:
            objects += response.yangjson
            err += response.errors
        return err, objects

    def cliconfig(self, cli):
        """Post of CLI config commands in text
            :param data: cli show
            :type data: str
            :return: Return the response object
            :rtype: str
        """
        message = ems_grpc_pb2.CliConfigArgs(cli=cli)
        response = self._stub.CliConfig(message, self._timeout, metadata=self._metadata)
        return response

    def commitreplace(self, cli="", yangjson=""):
        """Post of CLI config commands in text
            :param data: cli show or yang json
            :type data: str or json
            :return: Return the response object
            :rtype: str
        """
        if not cli:
            message = ems_grpc_pb2.CommitReplaceArgs(yangjson=yangjson)
        else:
            message = ems_grpc_pb2.CommitReplaceArgs(cli=cli)
        response = self._stub.CommitReplace(message, self._timeout, metadata=self._metadata)
        return response

    def showcmdtextoutput(self, cli):
        """ Get of CLI show commands in text
            :param data: cli show
            :type data: str
            :return: Return the response object
            :rtype: str
        """
        stub = ems_grpc_pb2.beta_create_gRPCExec_stub(self._channel)
        message = ems_grpc_pb2.ShowCmdArgs(cli=cli)
        responses = stub.ShowCmdTextOutput(message, self._timeout, metadata=self._metadata)
        objects, err = '', ''
        for response in responses:
            objects += response.output
            err += response.errors
        return err, objects

    def showcmdjsonoutput(self, cli):
        """ Get of CLI show commands in json
            :param data: cli show
            :type data: str
            :return: Return the response object
            :rtype: str
        """
        stub = ems_grpc_pb2.beta_create_gRPCExec_stub(self._channel)
        message = ems_grpc_pb2.ShowCmdArgs(cli=cli)
        responses = stub.ShowCmdJSONOutput(message, self._timeout, metadata=self._metadata)
        objects, err = '', ''
        for response in responses:
            objects += response.jsonoutput
            err += response.errors
        return err, objects
