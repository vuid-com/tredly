# A class to represent a tredly partition

# TODO: note that maxCpu and MaxRam are only set in ZFS and don't actually limit anything just yet

from objects.zfs.zfs import ZFSDataset
from includes.defines import *

import os

class Partition:
    # Constructor
    def __init__(self, name, maxHdd = None, maxCpu = None, maxRam = None, publicIps = [], ip4Whitelist = []):
        self.name = name
        self.maxHdd = int(maxHdd)    # int in megabytes
        self.maxRam = int(maxRam)    # int in megabytes
        
        # check if maxCpu was a percentage and apply accordingly
        if (maxCpu is not None):
            if (maxCpu.endswith('%')):
                # strip off the percentage and turn it into an int
                self.maxCpu = int(maxCpu.rstrip('%'))
            else:
                # this is in cores, so turn it into a percentage. 1 core == 100%
                self.maxCpu = int(maxCpu) * 100
        
        # lists
        self.publicIps = publicIps          # list of public ips assigned to this partition
        self.ip4Whitelist = ip4Whitelist    # list of ip addresses whitelisted for this partition
        
        # set up our dataset and mountpoint
        self.dataset = ZFS_TREDLY_PARTITIONS_DATASET + '/' + self.name
        self.mountpoint = TREDLY_PARTITIONS_MOUNT + '/' + self.name
        


    # Action: creates this partition within zfs
    #
    # Pre: 
    # Post: partition has been created
    #
    # Params: 
    #
    # Return: True if succeeded, False otherwise
    def create(self):
        ### pre flight checks
        
        # set up a zfs object
        zfsPartition = ZFSDataset(self.dataset, self.mountpoint)
        
        # ensure that this partition doesnt already exist
        if (zfsPartition.exists()):
            return False
        
        # End pre flight checks
        
        e_header("Creating partition " + self.name)

        e_note("Creating ZFS datasets")
        returnCode = True
        
        # create the partition dataset
        returnCode = (returnCode & zfsPartition.create())
        
        # create the child datasets of this partition
        
        # /cntr
        zfsPartitionContainers = ZFSDataset(self.dataset + '/' + TREDLY_CONTAINER_DIR_NAME, self.mountpoint + '/' + TREDLY_CONTAINER_DIR_NAME)
        returnCode = (returnCode & zfsPartitionContainers.create())
        
        # /data
        zfsPartitionData = ZFSDataset(self.dataset + '/' + TREDLY_PTN_DATA_DIR_NAME, self.mountpoint + '/' + TREDLY_PTN_DATA_DIR_NAME)
        returnCode = (returnCode & zfsPartitionData.create())
        
        # /remotecontainers
        zfsPartitionRemoteCntr = ZFSDataset(self.dataset + '/' + TREDLY_PTN_REMOTECONTAINERS_DIR_NAME, self.mountpoint + '/' + TREDLY_PTN_REMOTECONTAINERS_DIR_NAME)
        returnCode = (returnCode & zfsPartitionRemoteCntr.create())

        # /psnt
        zfsPartitionPersistentStorage = ZFSDataset(self.dataset + '/' + TREDLY_PERSISTENT_STORAGE_DIR_NAME, self.mountpoint + '/' + TREDLY_PERSISTENT_STORAGE_DIR_NAME)
        returnCode = (returnCode & zfsPartitionPersistentStorage.create())

        # create some default directories within the data dataset
        baseDataDir = self.mountpoint + '/' + TREDLY_PTN_DATA_DIR_NAME
        os.makedirs(baseDataDir + '/credentials')
        os.makedirs(baseDataDir + '/scripts')
        os.makedirs(baseDataDir + '/sslCerts')
        
        # set the partition name
        returnCode = (returnCode & zfsPartition.setProperty(ZFS_PROP_ROOT + ':partition', self.name))
        
        if (returnCode):
            e_success()
        else:
            e_error()
            return False

        # apply HDD restrictions
        if (self.maxHdd is not None):
            e_note("Applying HDD value " + str(self.maxHdd))
            
            if (zfsPartition.setProperty('quota', self.maxHdd) + 'M'):
                e_success()
            else:
                e_error()
                return False

        # apply CPU restrictions
        if (self.maxCpu is not None):
            e_note("Applying CPU value " + str(self.maxCpu) + '%')

            if (zfsPartition.setProperty(ZFS_PROP_ROOT + ':maxcpu', self.maxCpu)):
                e_success()
            else:
                e_error()
                return False

        # apply RAM restrictions
        if (self.maxRam is not None):
            e_note("Applying RAM value " + str(self.maxRam) + 'M')

            if (zfsPartition.setProperty(ZFS_PROP_ROOT + ':maxram', self.maxRam)):
                e_success()
            else:
                e_error()
                return False

        # apply ip4 whitelisting
        if (len(self.ip4Whitelist) > 0):
            e_note("Applying Whitelist.")
            
            
        '''
        # Set the whitelist
        if partition_ipv4whitelist_create _whitelistArray[@] "${_partitionName}"; then
            # apply whitelist to partition members
            if ipfw_container_update_partition_members "${_partitionName}"; then
                if [[ "${_silent}" != "true" ]]; then
                    e_success "Success"
                fi
            else
                if [[ "${_silent}" != "true" ]]; then
                    e_error "Failed"
                fi
            fi
        else
            if [[ "${_silent}" != "true" ]]; then
                e_error "Failed"
            fi
        fi
    fi
    '''
    '''
    TODO: add this to the tredly-host part
    # ensure received units are correct
    if [[ -n "${_partitionHDD}" ]]; then
        if ! is_valid_size_unit "${_partitionHDD}" "m,g"; then
            exit_with_error "Invalid HDD specification: ${_partitionHDD}. Please use the format HDD=<size><unit>, eg HDD=1G."
        fi
    fi
    if [[ -n "${_partitionCPU}" ]]; then
        # make sure it was an int or included a percentage
        if ! is_int "${_partitionCPU}" && [[ "${_partitionCPU: -1}" != '%' ]]; then
            exit_with_error "Invalid CPU specification: ${_partitionCPU}. Please use the format CPU=<int> or CPU=<int>%, eg CPU=1"
        fi
    fi
    if [[ -n "${_partitionRAM}" ]]; then
        if ! is_valid_size_unit "${_partitionRAM}" "m,g"; then
            exit_with_error "Invalid RAM specification: ${_partitionRAM}. Please use the format RAM=<size><unit>, eg RAM=1G."
        fi
    fi
'''
