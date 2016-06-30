# Performs actions requested by the user
import builtins
from subprocess import Popen, PIPE
import urllib.request
import os.path
import time
import argparse
import signal

from objects.tredly.partition import Partition
from includes.util import *
from includes.defines import *
from includes.output import *


class ActionModify:
    def __init__(self, subject, target, identifier, actionArgs):
        
        # check the subject of this action
        if (subject == "partition"):
            self.modifyPartition(target, actionArgs['maxCpu'], actionArgs['maxHdd'], actionArgs['maxRam'], actionArgs['ipv4Whitelist'],  actionArgs['publicIps'], actionArgs['partitionName'])
        else:
            e_error("No command " + subject + " found.")
            exit(1)

    # Create a partition
    def modifyPartition(self, partitionName, maxCpu = None, maxHdd = None, maxRam = None, ip4Whitelist = None, publicIps = None, newName = None):
        
        ### Pre flight checks
        # check that the data we received is correct
        if (maxCpu is not None):
            maxCpuValidate = maxCpu
            
            # strip off the percentage if it exists
            maxCpuValidate = maxCpuValidate.rstrip('%')
            
            if (not isInt(maxCpuValidate)):
                e_error("maxcpu value " + maxCpu + " is not valid")
                exit(1)
        
        if (maxHdd is not None):
            # make sure its a valid size unit
            if (not isValidSizeUnit(maxHdd)):
                e_error("maxhdd value " + maxHdd + " is not valid")
                exit(1)
        
        if (maxRam is not None):
            # make sure its a valid size unit
            if (not isValidSizeUnit(maxRam)):
                e_error("maxram value " + maxRam + " is not valid")
                exit(1)
        
        ip4WhitelistList = []
        clearWhitelist = False
        # if the whitelist is == clear then delete everything
        if (ip4Whitelist != 'clear') and (ip4Whitelist is not None):
            # turn the whitelist into a list of IPv4Address and validate at the same time
            # split up the CSV
            ip4WhitelistList = []
            for ip in ip4Whitelist.split(','):
                if (isValidIp4(ip.strip())):
                    ip4WhitelistList.append(IPv4Address(ip.strip()))
                else:
                    e_error("ipv4whitelist value " + ip + " is not valid" )
                    exit(1)
        elif (ip4Whitelist == "clear"):
            clearWhitelist = True
        
        # TODO: ensure these public ips arent already in use
        publicIpList = []
        # turn the publicIps var into a list of IPv4Address and validate at the same time
        if (publicIps is not None):
            for ip in publicIps.split(','):
                if (isValidIp4AndCidr(ip.strip())):
                    publicIpList.append(IPv4Interface(ip.strip()))
                else:
                    e_error("publicips value " + ip + " is not valid. Please enter values in the form <ip4>/<cidr> eg. 192.168.0.1/24" )
                    exit(1)
        
        #######
        # create a partition object
        partition = Partition(partitionName, maxHdd, maxCpu, maxRam, publicIpList, ip4WhitelistList, newName)
        
        e_header("Modifying partition " + partitionName)
        
        if (not partition.exists()):
            e_error("Partition does not exist.")
            exit(1)
        
        
        partition.modify(clearWhitelist)
