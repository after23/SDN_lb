#!/usr/bin/python


"""Grouptable example

              Switch2 ----switch4
            /                       \     
h1 ---Switch1                        Switch5-----h2
            \                       /
              --------Switch3 ------



# static arp entry addition

h1 arp -s 192.168.1.2 00:00:00:00:00:02
h2 arp -s 192.168.1.1 00:00:00:00:00:01



ryu stuff:

ryu-manager group_table_lb.py

"""

from mininet.topo import Topo
from mininet.net import Mininet
from mininet.log import setLogLevel
from mininet.cli import CLI
from mininet.node import OVSSwitch, Controller, RemoteController
from time import sleep


class toplogi(Topo):
    "Single switch connected to n hosts."
    def build(self):
        s1 = self.addSwitch('s1', protocols='OpenFlow13')


        h1 = self.addHost('h1', mac="00:00:00:11:11:11", ip="10.0.0.11/24")
        h2 = self.addHost('h2', mac="00:00:00:22:22:22", ip="10.0.0.22/24")
        h3 = self.addHost('h3', mac="00:00:00:33:33:33", ip="10.0.0.33/24")
        h4 = self.addHost('h4', mac="00:00:00:00:00:01", ip="10.0.0.1/24")
        h5 = self.addHost('h5', mac="00:00:00:00:00:02", ip="10.0.0.2/24")
        h6 = self.addHost('h6', mac="00:00:00:00:00:03", ip="10.0.0.3/24")
        h7 = self.addHost('h7', mac="00:00:00:00:00:04", ip="10.0.0.4/24")

        
        self.addLink(s1,h1,1,1)
        self.addLink(s1,h2,2,1) 
        self.addLink(s1,h3,3,1)


        self.addLink(s1,h4,4,1)
        self.addLink(s1,h5,5,1)
        self.addLink(s1,h6,6,1)
        self.addLink(s1,h7,7,1)
        

if __name__ == '__main__':
    setLogLevel('info')
    topo = topologi()
    c1 = RemoteController('c1', ip='127.0.0.1')
    net = Mininet(topo=topo, controller=c1)
    net.start()
    #sleep(5)
    #print("Topology is up, lets ping")
    #net.pingAll()
    CLI(net)
    net.stop()
