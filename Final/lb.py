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
from ryu.lib.packet.packet import Packet
from ryu.lib.packet import arp
from ryu.lib.packet import ethernet
from ryu.lib.packet import ether_types


class SimpleSwitch13(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    virtual_ip = "10.0.0.10"

    ser1_mac = "00:00:00:11:11:11"
    ser1_ip = "10.0.0.11"
    ser2_mac = "00:00:00:22:22:22"
    ser2_ip = "10.0.0.22"
    ser3_mac = "00:00:00:33:33:33"
    ser3_ip = "10.0.0.33"
    next_ser = ""
    cur_ser = ""

    ser_ip_to_port = {ser1_ip: 1, ser2_ip: 2, ser3_ip:3}
    ip_to_mac = {"10.0.0.1": "00:00:00:00:01",
                 "10.0.0.2": "00:00:00:00:02",
                 "10.0.0.3": "00:00:00:00:03",
                 "10.0.0.4": "00:00:00:00:04"
                }

    def __init__(self, *args, **kwargs):
        super(SimpleSwitch13, self).__init__(*args, **kwargs)
        self.mac_to_port = {}
        self.next_ser = self.ser1_ip
        self.cur_ser = self.ser1_ip

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)

    def add_flow_lb(self, datapath, packet, ofp_parser, ofp, in_port):
        srcIp = packet.get_protocol(arp.arp).src_ip

        # Don't push forwarding rules if an ARP request is received from a server.
        if srcIp == self.ser1_ip or srcIp == self.ser2_ip or srcIp == self.ser3_ip:
            return

        # Generate flow from host to server.
        match = ofp_parser.OFPMatch(in_port=in_port,
                                    ipv4_dst=self.virtual_ip,
                                    eth_type=0x0800)
        actions = [ofp_parser.OFPActionSetField(ipv4_dst=self.cur_ser),
                   ofp_parser.OFPActionOutput(self.ser_ip_to_port[self.cur_ser])]
        inst = [ofp_parser.OFPInstructionActions(ofp.OFPIT_APPLY_ACTIONS, actions)]
        
        mod = ofp_parser.OFPFlowMod(
            datapath=datapath,
            priority=100,
            buffer_id=ofp.OFP_NO_BUFFER,
            match=match,
            instructions=inst)

        datapath.send_msg(mod)

        # Generate reverse flow from server to host.
        match = ofp_parser.OFPMatch(in_port=self.ser_ip_to_port[self.cur_ser],
                                    ipv4_src=self.cur_ser,
                                    ipv4_dst=srcIp,
                                    eth_type=0x0800)
        actions = [ofp_parser.OFPActionSetField(ipv4_src=self.virtual_ip),
                   ofp_parser.OFPActionOutput(in_port)]
        inst = [ofp_parser.OFPInstructionActions(ofp.OFPIT_APPLY_ACTIONS, actions)]

        mod = ofp_parser.OFPFlowMod(
            datapath=datapath,
            priority=0,
            buffer_id=ofp.OFP_NO_BUFFER,
            match=match,
            instructions=inst)

        datapath.send_msg(mod)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match['in_port']

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocols(ethernet.ethernet)[0]

        if eth.ethertype == ether_types.ETH_TYPE_ARP:
            self.add_flow_lb(datapath, pkt, parser, ofproto, in_port)
            self.arp_response(datapath, pkt, eth, parser, ofproto, in_port)
            self.cur_ser = self.next_ser
            return
        else:
            return

    def arp_response(self, datapath, packet, eth, parser, ofproto, in_port):
        arp_packet = packet.get_protocol(arp.arp)
        dstIp = arp_packet.src_ip
        srcIp = arp_packet.dst_ip
        dstMac = eth.src

<<<<<<< HEAD
        if dstIp != self.ser1_ip and dstIp != self.ser2.ip and dstIp != self.ser3_ip:
=======
        if dstIp != self.ser1_ip or dstIp != self.ser2_ip or dstIp != self.ser3_ip:
>>>>>>> fabd157fcd1c8b3803a60cc180d23f731c725bb9
            if self.next_ser == self.ser1_ip:
                srcMac = self.ser1_mac
                self.next_ser = self.ser2_ip
            elif self.next_ser == self.ser2_ip:
                srcMac = self.ser2_mac
            else:
                srcMac = self.ser3_mac
        else:
            srcMac = self.ip_to_mac[srcIp]

        e = ethernet.ethernet(dstMac, srcMac, ether_types.ETH_TYPE_ARP)
        a = arp.arp(1, 0x0800, 6, 4, 2, srcMac, srcIp, dstMac, dstIp)
        p = Packet()
        p.add_protocol(e)
        p.add_protocol(a)
        p.serialize()

        actions= [parser.OFPActionOutput(ofproto.OFPP_IN_PORT)]
        out = parser.OFPPacketOut(datapath=datapath, buffer_id = ofproto.OFP_NO_BUFFER, in_port=in_port, actions = actions, data=p.data)
        datapath.send_msg(out)