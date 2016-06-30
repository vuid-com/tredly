# A class to represent a tredly partition

# TODO: note that maxCpu and MaxRam are only set in ZFS and don't actually limit anything just yet

from objects.zfs.zfs import ZFSDataset
from objects.tredly.container import Container
from includes.defines import *
from includes.output import *
from objects.nginx.layer7proxy import *

from subprocess import Popen, PIPE
import os
import re

class Partition:
    # Constructor
    def __init__(self, name, maxHdd = None, maxCpu = None, maxRam = None, publicIps = [], ip4Whitelist = [], newName = None):
        # set up our dataset and mountpoint
        self.dataset = ZFS_TREDLY_PARTITIONS_DATASET + '/' + name
        self.mountpoint = TREDLY_PARTITIONS_MOUNT + '/' + name
        
        # set up a zfs object to use in this object
        self.zfs = ZFSDataset(self.dataset, self.mountpoint)
        
        # if this dataset exists then load all data from zfs
        if (self.exists()):
            self.loadFromZFS()
        
        # overwrite hte values loaded from zfs
        self.name = name
        self.newName = newName
        self.maxHdd = maxHdd    # in megabytes
        self.maxRam = maxRam    # in megabytes
        
        # check if maxCpu was a percentage and apply accordingly
        if (maxCpu is not None):
            if (maxCpu.endswith('%')):
                # strip off the percentage and turn it into an int
                self.maxCpu = maxCpu.rstrip('%')
            else:
                # this is in cores, so turn it into a percentage. 1 core == 100%
                self.maxCpu = str(int(maxCpu) * 100)
        
        # lists
        if (publicIps is not None):
            self.publicIps = publicIps          # list of public ips assigned to this partition
        else:
            self.publicIps = []
            
        if (ip4Whitelist is not None) and (len(ip4Whitelist) > 0):
            self.ip4Whitelist = ip4Whitelist    # list of ip addresses whitelisted for this partition
        

    # Action: load all values from zfs into this object
    #
    # Pre: partition exists
    # Post: this object has been populated with values from ZFS
    #
    # Params:
    #
    # Return: True if successful, False otherwise
    def loadFromZFS(self):
        # return false if this dataset does not exist
        if (not self.exists()):
            return False
        
        # name is mandatory
        self.name = self.zfs.getProperty(ZFS_PROP_ROOT + ':partition')
        
        self.maxHdd = self.zfs.getProperty('quota')
        self.maxRam = self.zfs.getProperty(ZFS_PROP_ROOT + ':maxram')
        self.maxCpu = self.zfs.getProperty(ZFS_PROP_ROOT + ':maxcpu')

        # zfs arrays
        self.publicIps = self.zfs.getArray(ZFS_PROP_ROOT + '.publicips').items()
        self.ip4Whitelist = self.zfs.getArray(ZFS_PROP_ROOT + '.ptn_ip4whitelist').items()

        return True
    
    # Action: get a list of containers within this partition
    #
    # Pre: partition exists
    # Post: 
    #
    # Params:
    #
    # Return: list of Container objects
    def getContainers(self):
        # form the base dataset to search in
        dataset = self.dataset + "/" + TREDLY_CONTAINER_DIR_NAME
        
        # get a list of the containers
        cmd = ['zfs', 'list', '-H', '-r', '-o' 'name', dataset]
        process = Popen(cmd, stdin=PIPE, stdout=PIPE, stderr=PIPE)
        stdOut, stdErr = process.communicate()
        if (process.returncode != 0):
            e_error("Failed to get list of partition members")
            return None
        
        # convert stdout to string
        stdOut = stdOut.decode(encoding='UTF-8').rstrip()
        
        # create a list to pass back
        containerList = []
        
        # loop over the results looking for our value
        for line in iter(stdOut.splitlines()):
            # check if it matches our partition
            if (re.match("^" + dataset + "/.*$", line)):
                # get the uuid and append to our list
                uuid = line.split('/')[-1]
                
                container = Container()
                
                # make the container populate itself from zfs
                container.loadFromZFS(dataset + "/" + uuid)
                
                # append to the list
                containerList.append(container)
        
        return containerList
    
    # Action: checks to see if this partition exists already or not
    #
    # Pre: 
    # Post: 
    #
    # Params: 
    #
    # Return: True if exists, False otherwise
    def exists(self):
        return self.zfs.exists()
    
    # Action: creates this partition
    #
    # Pre: 
    # Post: partition has been created
    #
    # Params: 
    #
    # Return: True if succeeded, False otherwise
    def create(self):
        ### pre flight checks
        
        # ensure that this partition doesnt already exist
        if (self.exists()):
            return False
        
        # End pre flight checks

        e_note("Creating ZFS datasets")
        returnCode = True
        
        # create the partition dataset
        returnCode = (returnCode & self.zfs.create() & self.zfs.mount())
        
        # create the child datasets of this partition
        
        # /cntr
        zfsPartitionContainers = ZFSDataset(self.dataset + '/' + TREDLY_CONTAINER_DIR_NAME, self.mountpoint + '/' + TREDLY_CONTAINER_DIR_NAME)
        returnCode = (returnCode & zfsPartitionContainers.create() & zfsPartitionContainers.mount())
        
        # /data
        zfsPartitionData = ZFSDataset(self.dataset + '/' + TREDLY_PTN_DATA_DIR_NAME, self.mountpoint + '/' + TREDLY_PTN_DATA_DIR_NAME)
        returnCode = (returnCode & zfsPartitionData.create() & zfsPartitionData.mount())
        
        # /remotecontainers
        zfsPartitionRemoteCntr = ZFSDataset(self.dataset + '/' + TREDLY_PTN_REMOTECONTAINERS_DIR_NAME, self.mountpoint + '/' + TREDLY_PTN_REMOTECONTAINERS_DIR_NAME)
        returnCode = (returnCode & zfsPartitionRemoteCntr.create() & zfsPartitionRemoteCntr.mount())

        # /psnt
        zfsPartitionPersistentStorage = ZFSDataset(self.dataset + '/' + TREDLY_PERSISTENT_STORAGE_DIR_NAME, self.mountpoint + '/' + TREDLY_PERSISTENT_STORAGE_DIR_NAME)
        returnCode = (returnCode & zfsPartitionPersistentStorage.create() & zfsPartitionPersistentStorage.mount())
        self.zfs.listChildren()
        # create some default directories within the data dataset
        baseDataDir = self.mountpoint + '/' + TREDLY_PTN_DATA_DIR_NAME
        os.makedirs(baseDataDir + '/credentials')
        os.makedirs(baseDataDir + '/scripts')
        os.makedirs(baseDataDir + '/sslCerts')
        
        # set the partition name
        returnCode = (returnCode & self.zfs.setProperty(ZFS_PROP_ROOT + ':partition', self.name))
        
        if (returnCode):
            e_success()
        else:
            e_error()
            return False

        # apply HDD restrictions
        if (self.maxHdd is not None):
            e_note("Applying HDD value " + str(self.maxHdd))
            
            if (self.applyMaxHdd()):
                e_success()
            else:
                e_error()
                return False

        # apply CPU restrictions
        if (self.maxCpu is not None):
            e_note("Applying CPU value " + str(self.maxCpu) + '%')

            if (self.applyMaxCpu()):
                e_success()
            else:
                e_error()
                return False

        # apply RAM restrictions
        if (self.maxRam is not None):
            e_note("Applying RAM value " + str(self.maxRam))

            if (self.applyMaxRam()):
                e_success()
            else:
                e_error()
                return False

        # apply ip4 whitelisting
        if (len(self.ip4Whitelist) > 0):
            e_note("Applying Whitelist")
    
            if (self.applyWhitelist()):
                e_success()
            else:
                e_error()
                return False
        
        # apply public ips
        if (len(self.publicIps) > 0):
            e_note("Applying Public IPs")

            if (self.applyPublicIps()):
                e_success()
            else:
                e_error()
                return False
        
        # we made it to the end so return true
        return True

    # Action: sets the maxhdd value in ZFS
    #
    # Pre: this partition exists
    # Post: partition has been updated
    #
    # Params: 
    #
    # Return: True if succeeded, False otherwise
    def applyMaxHdd(self):
        if (not self.zfs.setProperty('quota', self.maxHdd)):
            return False
        
        return True

    # Action: sets the maxcpu value in ZFS
    #
    # Pre: this partition exists
    # Post: partition has been updated
    #
    # Params: 
    #
    # Return: True if succeeded, False otherwise
    def applyMaxCpu(self):
        if (not self.zfs.setProperty(ZFS_PROP_ROOT + ':maxcpu', self.maxCpu)):
            return False
        
        return True

    # Action: sets the maxram value in ZFS
    #
    # Pre: this partition exists
    # Post: partition has been updated
    #
    # Params: 
    #
    # Return: True if succeeded, False otherwise
    def applyMaxRam(self):
        if (not self.zfs.setProperty(ZFS_PROP_ROOT + ':maxram', self.maxRam)):
            return False
        
        return True

    # Action: sets the public ips up for this partition
    #
    # Pre: this partition exists
    # Post: public IPs have been set up
    #
    # Params: 
    #
    # Return: True if succeeded, False otherwise
    
    # this will set zfs and set up the public ips on an interface
    # we will need a command to remove public ips from a partition
    def applyPublicIps(self):
        # TODO: set these ips up on an interface. Epair? Bridge? lifNetwork? Undecided as yet
        
        # set the zfs property array
        for ip in self.publicIps:
            # set it in zfs and get the status
            if (not self.zfs.appendArray(ZFS_PROP_ROOT + '.publicips', ip)):
                return False

        return True

    # Action: modifies this partition
    #
    # Pre: this partition exists
    # Post: partition has been modified
    #
    # Params: clearWhitelist - whether or not to clear out the whitelist, regardless of the value of self.ip4whitelist
    #
    # Return: True if succeeded, False otherwise
    def modify(self, clearWhitelist = False):
        ### pre flight checks
        
        # ensure that this partition exists as we are modifying it
        if (not self.exists()):
            e_error("Partition " + self.name + " does not exist")
            return False
        
        # ensure that the new partition name doesnt already exist
        if (self.newName is not None):
            newNamePartition = Partition(self.newName)
            if (newNamePartition.exists()):
                e_error("Cannot rename partition: partition " + self.newName + " already exists")
                return False
        
        # ensure there are no containers built within this partition
        #zfsContainerList = ZFSDataset(self.dataset + '/' + TREDLY_CONTAINER_DIR_NAME, self.mountpoint + '/' + TREDLY_CONTAINER_DIR_NAME)
        #containerDatasets = zfsContainerList.listChildren()
        #if (len(containerDatasets) > 0):
            #e_error("Partition " + self.name + " currently has built containers. Please destroy them and run this command again.")
            #return False
        
        # End pre flight checks
        
        # apply HDD restrictions
        if (self.maxHdd is not None):
            e_note("Applying HDD value " + str(self.maxHdd))
            
            if (self.applyMaxHdd()):
                e_success()
            else:
                e_error()
                return False

        # apply CPU restrictions
        if (self.maxCpu is not None):
            e_note("Applying CPU value " + str(self.maxCpu) + '%')

            if (self.applyMaxCpu()):
                e_success()
            else:
                e_error()
                return False

        # apply RAM restrictions
        if (self.maxRam is not None):
            e_note("Applying RAM value " + str(self.maxRam))

            if (self.applyMaxRam()):
                e_success()
            else:
                e_error()
                return False

        e_note("Applying Whitelist")
        
        if (self.applyWhitelist(clearWhitelist)):
            e_success()
        else:
            e_error()
            return False
        
        # apply public ips
        if (len(self.publicIps) > 0):
            e_note("Applying Public IPs")

            if (self.applyPublicIps()):
                e_success()
            else:
                e_error()
                return False
        
        # if the new name was set then rename it
        if (self.newName is not None):
            if (self.zfs.rename(self.newName)):
                # change the partition name
                self.zfs.setProperty(ZFS_PROP_ROOT + ':partition', self.newName)
                
                e_success()
            else:
                e_error()
                return False
            
        return True

    # Action: apply the container whitelist to zfs and all containers in this partition
    #
    # Pre: partition exists
    # Post: containers within partition have had their partition whitelists updated
    #
    # Params: 
    #
    # Return: True if succeeded, False otherwise
    # TODO: untested, required for modify
    def applyWhitelist(self, clearWhitelist = False):

        if (clearWhitelist):
            # remove all data from zfs array
            if (not self.zfs.unsetArray(ZFS_PROP_ROOT + '.ptn_ip4whitelist')):
                return False
        else:
            # set the ips in zfs
            for ip in self.ip4Whitelist:
                if (not self.zfs.appendArray(ZFS_PROP_ROOT + '.ptn_ip4whitelist', ip)):
                    return False

        # get a list of containers in this partition
        containers = self.getContainers()

        # loop over the containers and apply their whitelists to ipfw
        for container in containers:
            # flush the table before applying new rules
            if (not container.firewall.flushTable(CONTAINER_IPFW_WL_TABLE_PARTITION)):
                e_error("Failed to flush table " + CONTAINER_IPFW_WL_TABLE_PARTITION + " in container.")
            
            # apply to IPFW
            for ip4 in self.ip4Whitelist:
                if (not container.firewall.appendTable(CONTAINER_IPFW_WL_TABLE_PARTITION, str(ip4))):
                    return False
            
            # apply the firewall table
            if (not container.firewall.apply()):
                return False
        
        # apply to layer 7 proxy
        l7Proxy = Layer7Proxy()

        if (clearWhitelist):
            l7Proxy.registerAccessFile('/usr/local/etc/nginx/access/ptn_' + self.name, [], False, True)
        else:
            # set up the access file for the partition
            l7Proxy.registerAccessFile('/usr/local/etc/nginx/access/ptn_' + self.name, self.ip4Whitelist, False, True)

        l7Proxy.reload()

        return True