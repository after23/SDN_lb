# Copyright (C) 2011 Nippon Telegraph and Telephone Corporation.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet
from ryu.lib.packet import ether_types
import logging
import random
from ryu.lib.packet import ipv4
from ryu.lib.packet import tcp
from ryu.lib.packet import arp
from ryu.lib.packet import icmp
from ryu.app import simple_switch_13


class SimpleSwitch13(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(SimpleSwitch13, self).__init__(*args, **kwargs)
        self.mac_to_port = {}
        self.servers = []
        self.servers.append({'ip':"10.0.0.1", 'mac':"00:00:00:00:00:01", 'port':1})
        self.servers.append({'ip':"10.0.0.2", 'mac':"00:00:00:00:00:02", 'port':2})
        self.servers.append({'ip':"10.0.0.3", 'mac':"00:00:00:00:00:03", 'port':3})
        self.dummyIP = "10.0.0.100"
        self.dummyMAC = "AB:BC:CD:EF:F1:12"
        self.serverNumber = 0
        self.logger.info("Initialized new Object instance data")

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # install table-miss flow entry
        #
        # We specify NO BUFFER to max_len of the output action due to
        # OVS bug. At this moment, if we specify a lesser number, e.g.,
        # 128, OVS will send Packet-In with invalid buffer_id and
        # truncated packet data. In that case, we cannot output packets
        # correctly.  The bug has been fixed in OVS v2.1.0.
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
                                          ofproto.OFPCML_NO_BUFFER)]
        self.add_flow(datapath, 0, match, actions)

    def add_flow(self, datapath, priority, match, actions, buffer_id=None):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS,
                                             actions)]
        if buffer_id:
            mod = parser.OFPFlowMod(datapath=datapath, buffer_id=buffer_id,
                                    priority=priority, match=match,
                                    instructions=inst)
        else:
            mod = parser.OFPFlowMod(datapath=datapath, priority=priority,
                                    match=match, instructions=inst)
        datapath.send_msg(mod)
    
    def handle_arp_for_server(self, dmac, dip):
        self.logger.info("Handling ARP Reply for dummy Server IP")
        #handle arp request for Dummy Server IP
        #checked Wireshark for sample pcap for arp-reply
        #build arp packet - format source web link included in reference
        hrdw_type = 1 #Hardware Type: ethernet 10mb
        protocol = 2048 #Layer 3 type: Internet Protocol
        hrdw_add_len = 6 # length of mac
        prot_add_len = 4 # lenght of IP
        opcode = 2 # arp reply
        sha = self.dummyMAC #sender address
        spa = self.dummyIP #sender IP
        tha = dmac #target MAC
        tpa = dip #target IP
        
        ether_type = 2054 #ethertype ARP
        
        pack = packet.Packet()
        eth_frame = ethernet.ethernet(dmac, sha, ether_type)
        arp_rpl_frame = arp.arp(hrdw_type, protocol, hrdw_add_len, prot_add_len, opcode, sha, spa, tha, tpa)
        pack.add_protocol(eth_frame)
        pack.add_protocol(arp_rpl_frame)
        pack.serialize()
        self.logger.info("Done handling ARP Reply")
        return pack

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        # If you hit this you might want to increase
        # the "miss_send_length" of your switch
        if ev.msg.msg_len < ev.msg.total_len:
            self.logger.debug("packet truncated: only %s of %s bytes",
                              ev.msg.msg_len, ev.msg.total_len)
        
        if self.serverNumber == 3:
            self.serverNumber = 0
        
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match['in_port']

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocols(ethernet.ethernet)[0]

        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            # ignore lldp packet
            return
        dst = eth.dst
        src = eth.src

        dpid = datapath.id
        self.mac_to_port.setdefault(dpid, {})

        self.logger.info("packet in %s %s %s %s", dpid, src, dst, in_port)

        # learn a mac address to avoid FLOOD next time.
        self.mac_to_port[dpid][src] = in_port

        if dst in self.mac_to_port[dpid]:
            out_port = self.mac_to_port[dpid][dst]
        else:
            out_port = ofproto.OFPP_FLOOD

        actions = [parser.OFPActionOutput(out_port)]

        # install a flow to avoid packet_in next time
        if out_port != ofproto.OFPP_FLOOD:
            match = parser.OFPMatch(in_port=in_port, eth_dst=dst, eth_src=src)
            # verify if we have a valid buffer_id, if yes avoid to send both
            # flow_mod & packet_out
            if msg.buffer_id != ofproto.OFP_NO_BUFFER:
                self.add_flow(datapath, 1, match, actions, msg.buffer_id)
                return
            else:
                self.add_flow(datapath, 1, match, actions)
        data = None
        if msg.buffer_id == ofproto.OFP_NO_BUFFER:
            data = msg.data

        out = parser.OFPPacketOut(datapath=datapath, buffer_id=msg.buffer_id,
                                  in_port=in_port, actions=actions, data=data)
        datapath.send_msg(out)

        if eth.ethertype == 2054:
            arp_head = pkt.get_protocols(arp.arp)[0]
            if arp_head.dst_ip == self.dummyIP:
                #dmac and dIP for ARP Reply
                a_r_ip = arp_head.src_ip
                a_r_mac = arp_head.src_mac
                arp_reply = self.handle_arp_for_server(a_r_mac, a_r_ip)
                actions = [parser.OFPActionOutput(in_port)]
                buffer_id = msg.buffer_id #id assigned by datapath - keep track of buffered packet
                port_no = ofproto.OFPP_ANY #for any port number
                data = arp_reply.data
                #self.logger.info(data)
                out = parser.OFPPacketOut(datapath=datapath, buffer_id=buffer_id, in_port=port_no, actions=actions, data=data)
                datapath.send_msg(out)
                self.logger.info("ARP Request handled")				
                return
        
        choice_ip = self.servers[self.serverNumber]['ip']
        choice_mac = self.servers[self.serverNumber]['mac']
        choice_server_port = self.servers[self.serverNumber]['port']
        self.logger.info("Server Choice details: \tIP is %s\tMAC is %s\tPort is %s", choice_ip, choice_mac, choice_server_port)

        self.logger.info("Redirecting data request packet to one of the Servers")
        #Redirecting data request packet to Server
        if eth.ethertype == 2048:
            ip_head = pkt.get_protocols(ipv4.ipv4)[0]
            match = parser.OFPMatch(in_port=in_port, eth_type=eth.ethertype, eth_src=eth.src, eth_dst=eth.dst, ip_proto=ip_head.proto, ipv4_src=ip_head.src, ipv4_dst=ip_head.dst)
            self.logger.info("Data request being sent to Server: IP: %s, MAC: %s", choice_ip, choice_mac)
            actions = [parser.OFPActionSetField(eth_dst=choice_mac), parser.OFPActionSetField(ipv4_dst=choice_ip), parser.OFPActionOutput(choice_server_port)]
            instruction1 = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
            #cookie = random.randint(0, 0xffffffffffffffff)
            flow_mod = parser.OFPFlowMod(datapath=datapath, match=match, idle_timeout=5, instructions=instruction1, buffer_id = msg.buffer_id)
            datapath.send_msg(flow_mod)

            self.logger.info("Redirection done...1")
            self.logger.info("Redirecting data reply packet to the host")
            #Redirecting data reply to respecitve Host
            match = parser.OFPMatch(in_port=choice_server_port, eth_type=eth.ethertype, eth_src=choice_mac, eth_dst=eth.dst, ip_proto=ip_head.proto, ipv4_src=choice_ip, ipv4_dst=ip_head.dst)
            self.logger.info("Data reply coming from Server: IP: %s, MAC: %s", choice_ip, choice_mac)
            actions = [parser.OFPActionSetField(eth_src=self.dummyMAC), parser.OFPActionSetField(ipv4_src=self.dummyIP), parser.OFPActionOutput(in_port) ]

            instruction2 = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
            #cookie = random.randint(0, 0xffffffffffffffff)

            flow_mod2 = parser.OFPFlowMod(datapath=datapath, match=match, idle_timeout=5, instructions=instruction2)
            datapath.send_msg(flow_mod2)

        self.serverNumber = self.serverNumber + 1
        self.logger.info("Redirecting done...2")
        self.logger.info(self.mac_to_port)