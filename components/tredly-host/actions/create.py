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


class ActionCreate:
    def __init__(self, subject, target, identifier, actionArgs):
        
        # check the subject of this action
        if (subject == "partition"):
            '''
            CPU)
                    _partition_cpu="${value}"
                ;;
                HDD)
                    _partition_hdd="${value}"
                ;;
                RAM)
                    _partition_ram="${value}"
                ;;
                ipv4Whitelist)
                    echo "${value}"
                    _partition_ip4whitelist="${value}"
                ;;
            '''
            
            self.createPartition(target, actionArgs['maxCpu'], actionArgs['maxHdd'], actionArgs['maxRam'], actionArgs['ipv4Whitelist'],  actionArgs['publicIps'])
        else:
            e_error("No command " + subject + " found.")
            exit(1)

    # Create a partition
    def createPartition(self, partitionName, maxCpu = None, maxHdd = None, maxRam = None, ip4Whitelist = [], publicIps = []):
        
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
        
        if (ip4Whitelist is not None):
            for ip in ip4Whitelist:
                if (not isValidIp4(ip)):
                    e_error("ipv4whitelist value " + ip + " is not valid")
                    exit(1)
                    
        if (publicIps is not None):
            for ip in publicIps:
                if (not isValidIp4(ip)):
                    e_error("publicips value " + ip + " is not valid")
                    exit(1)
        #######
            
        # create a partition object
        partition = Partition(partitionName, maxHdd, maxCpu, maxRam, publicIps, ip4Whitelist)
        
        e_header("Creating partition " + partitionName)
        
        if (partition.exists()):
            e_error("Partition already exists.")
            exit(1)
        
        partition.create()
