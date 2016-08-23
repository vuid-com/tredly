# A class to retrieve data from a tredly host
from subprocess import Popen, PIPE
import re

from objects.tidycmd.tidycmd import *

from includes.util import *
from includes.defines import *
from includes.output import *

class TredlyHost:

    # Action: return a list of partition names on this host
    #
    # Pre:
    # Post:
    #
    # Params:
    #
    # Return: list of strings
    def getPartitionNames(self):
        # create a list to pass back
        partitionNames = []

        # get a list of the properties for these group members
        cmd = ['zfs', 'list', '-H', '-o' 'name', '-r', '-d', '1', ZFS_TREDLY_PARTITIONS_DATASET]
        process = Popen(cmd,  stdin=PIPE, stdout=PIPE, stderr=PIPE)
        stdOut, stdErr = process.communicate()
        if (process.returncode != 0):
            e_error("Failed to get list of partition names")

        # convert stdout to string
        stdOut = stdOut.decode(encoding='UTF-8').rstrip();

        for line in stdOut.splitlines():
            # strip off the dataset part
            line = line.replace(ZFS_TREDLY_PARTITIONS_DATASET, '').strip()

            # check if the line still contains data
            if (len(line) > 0):
                # and now strip the slash which should be at the beginning
                line = line.lstrip('/')

                partitionNames.append(line)

        return partitionNames

    # Action: get a list of ip addresses of all containers in the given group/partition
    #
    # Pre:
    # Post:
    #
    # Params: containerGroup - the containergroup to search for
    #         partitionName - the partition name to search for
    #
    # Return: list of strings (ip addresses)
    def getContainerGroupContainerIps(self, containerGroup, partitionName):
        # form the base dataset to search in
        dataset = ZFS_TREDLY_PARTITIONS_DATASET + "/" + partitionName + '/cntr'

        # and the property
        datasetProperty = ZFS_PROP_ROOT +':ip4_addr'

        # get a list of uuids in this group
        groupMemberUUIDs = self.getContainerGroupContainerUUIDs(containerGroup, partitionName)

        # create a list to pass back
        ipList = []

        # loop over htem and get the data
        for uuid in groupMemberUUIDs:
            # get a list of the properties for these group members
            cmd = ['zfs', 'get', '-H', '-r', '-o' 'name,value', datasetProperty, dataset + '/' + uuid]
            process = Popen(cmd,  stdin=PIPE, stdout=PIPE, stderr=PIPE)
            stdOut, stdErr = process.communicate()
            if (process.returncode != 0):
                e_error("Failed to get list of containergroup ips")

            # convert stdout to string
            stdOut = stdOut.decode(encoding='UTF-8').rstrip();

            # extract the data if it exists
            if (re.match("^" + dataset + '/' + uuid, stdOut)):
                # extract the value part
                ip4Part = stdOut.split()[1]

                # extract the ip
                regex = '^(\w+)\|([\w.]+)\/(\d+)$'
                m = re.match(regex, ip4Part)

                if (m is not None):
                    ipList.append(m.group(2))

        return ipList

    # Action: get a list of container uuids within a container group and partition
    #
    # Pre:
    # Post:
    #
    # Params: containerGroup - the container group to search for
    #         partitionName - the partition name to search for
    #
    # Return: list of strings (uuids)
    def getContainerGroupContainerUUIDs(self, containerGroup, partitionName):
        # form the base dataset to search in
        dataset = ZFS_TREDLY_PARTITIONS_DATASET + "/" + partitionName

        # and the property
        datasetProperty = ZFS_PROP_ROOT +':containergroupname'

        # get a list of the properties
        cmd = ['zfs', 'get', '-H', '-r', '-o' 'name,value', datasetProperty, dataset]
        process = Popen(cmd,  stdin=PIPE, stdout=PIPE, stderr=PIPE)
        stdOut, stdErr = process.communicate()
        if (process.returncode != 0):
            e_error("Failed to get list of containergroup members")

        # convert stdout to string
        stdOut = stdOut.decode(encoding='UTF-8').rstrip();

        # create a list to pass back
        containerList = []

        # loop over the results looking for our value
        for line in iter(stdOut.splitlines()):
            # check if it matches our containergroup
            if (re.match("^.*\s" + containerGroup + "$", line)):
                # extract the dataset part
                datasetPart = line.split()[0]

                # get the uuid and append to our list
                containerList.append(datasetPart.split('/')[-1])

        return containerList

    # Action: get a list of containers within a partition
    #
    # Pre:
    # Post:
    #
    # Params: partitionName - the partition to search in
    #
    # Return: list of strings (uuids)
    def getPartitionContainerUUIDs(self, partitionName):
        # form the base dataset to search in
        dataset = ZFS_TREDLY_PARTITIONS_DATASET + "/" + partitionName + "/" + TREDLY_CONTAINER_DIR_NAME

        # get a list of the containers
        cmd = ['zfs', 'list', '-H', '-r', '-o' 'name', dataset]
        process = Popen(cmd, stdin=PIPE, stdout=PIPE, stderr=PIPE)
        stdOut, stdErr = process.communicate()
        if (process.returncode != 0):
            e_error("Failed to get list of partition members")

        # convert stdout to string
        stdOut = stdOut.decode(encoding='UTF-8').rstrip()

        # create a list to pass back
        containerList = []

        # loop over the results looking for our value
        for line in iter(stdOut.splitlines()):
            # check if it matches our containergroup
            if (re.match("^" + dataset + "/.*$", line)):
                # get the uuid and append to our list
                containerList.append(line.split('/')[-1])

        return containerList

    # Action: check if a container exists in a given partition
    #
    # Pre:
    # Post:
    #
    # Params: partitionName - the partition to search in
    #
    # Return: True if exists, False otherwise
    def containerExists(self, uuid, partitionName = None):
        if (uuid is None):
            return False
        if (len(uuid) == 0):
            return False

        # find the partition name if partition name was empty
        if (partitionName is None):
            # get the partition name
            partitionName = self.getContainerPartition(uuid)

            # if None was returned then the container doesnt exist
            if (partitionName is None):
                return False

        # get a list of containers in this partition
        containerUUIDs = self.getPartitionContainerUUIDs(partitionName)

        # check if it exists in the array
        if (uuid in containerUUIDs):
            return True

        return False

    # Action: finds the partition that the given uuid resides on
    #
    # Pre:
    # Post:
    #
    # Params: uuid - the uuid to search for
    #
    # Return: string (partition name)
    def getContainerPartition(self, uuid):
        zfsCmd = ['zfs', 'list', '-d6', '-rH', '-o', 'name', ZFS_TREDLY_PARTITIONS_DATASET]
        zfsResult = Popen(zfsCmd, stdout=PIPE)
        stdOut, stdErr = zfsResult.communicate()

        # convert stdout to string
        stdOutString = stdOut.decode("utf-8").strip()

        # loop over the results looking for our uuid
        for line in stdOutString.splitlines():
            line.strip()
            if (line.endswith(TREDLY_CONTAINER_DIR_NAME + "/" + uuid)):
                # found it so extract the partition name
                partitionName = line.replace(ZFS_TREDLY_PARTITIONS_DATASET + '/', '')

                partitionName = partitionName.replace('/' + TREDLY_CONTAINER_DIR_NAME + '/' + uuid, '')

                return partitionName

        # return none if nothing found
        return None

    # Action: search for all containers that have a given zfs array
    #
    # Pre:
    # Post:
    #
    # Params: datasetProperty - the property to search in
    #         string - the array name to search for
    #
    # Return: set of strings (uuids). a set is used here to enforce uniqueness
    def getContainersWithArray(self, datasetProperty, arrayName):
        # form the base dataset to search in
        dataset = ZFS_TREDLY_PARTITIONS_DATASET

        cmd =  ['zfs', 'get', '-H', '-r', '-o' 'name,value,property', 'all', dataset]
        result = Popen(cmd, stdout=PIPE)
        stdOut, stdErr = result.communicate()

        # convert stdout to string
        stdOutString = stdOut.decode("utf-8").strip()
        uuids = []

        # loop over the results looking for our dataset
        for line in stdOutString.splitlines():
            line.strip()

            if (re.search(datasetProperty + ':\d+$', line)):
                # split it up into elements
                lineElements = line.split()

                # match 2nd element to the arrayName
                # and the 3rd element to the dataset property name
                if (lineElements[1] == arrayName) and (re.match(datasetProperty + ':\d+$', lineElements[2])):
                    # found it so extract the uuid from the first element and append to our array
                    uuids.append(lineElements[0].split('/')[-1])

        # return a set as we are only after unique values
        return set(uuids)

    # Action: find the uuid of a contaienr with containerName
    #
    # Pre:
    # Post:
    #
    # Params: partitionName - the partition to search in
    #         containerName - the name of the container to search for
    #
    # Return: string (uuid)
    def getUUIDFromContainerName(self, partitionName, containerName):
        # form the base dataset to search in
        dataset = ZFS_TREDLY_PARTITIONS_DATASET + "/" + partitionName + "/" + TREDLY_CONTAINER_DIR_NAME

        # get a list of the containers
        zfsCmd = ['zfs', 'get', '-H', '-r', '-o', 'name,property,value', 'all', dataset]
        grepCmd = ['grep', '-F', ZFS_PROP_ROOT + ':containername']

        zfsProcess = Popen(zfsCmd, stdin=PIPE, stdout=PIPE, stderr=PIPE)
        grepProcess = Popen(grepCmd, stdin=zfsProcess.stdout, stdout=PIPE, stderr=PIPE)

        stdOut, stdErr = grepProcess.communicate()

        if (grepProcess.returncode != 0):
            return None

        # convert stdout to string
        stdOut = stdOut.decode(encoding='UTF-8').rstrip()

        # loop over the results looking for our value
        for line in iter(stdOut.splitlines()):
            # split up the line
            splitLine = line.split()

            # check if it matches our containergroup
            if (splitLine[2] == containerName):
                # get the uuid and append to our list
                return splitLine[0].split('/')[-1]

    # Action: find the containername of a container with uuid
    #
    # Pre: container exists
    # Post:
    #
    # Params: uuid - the uuid of the container to search for
    #         partitionName - the partition to search in
    #
    # Return: string (container name)
    def getContainerNameFromUUID(self, uuid, partitionName = None):
        # if partition name wasnt given then get the partition name
        if (partitionName is None):
            partitionName = self.getContainerPartition(uuid)

        # extract the container name from zfs
        dataset = ZFS_TREDLY_PARTITIONS_DATASET + "/" + partitionName + "/" + TREDLY_CONTAINER_DIR_NAME + '/' + uuid

        zfsContainer = ZFSDataset(dataset)

        return zfsContainer.getProperty(ZFS_PROP_ROOT + ':containername')

    # Action: get a list of all container UUIDs on this host
    #
    # Pre:
    # Post: list has been returned
    #
    # Params:
    #
    # Return: list (uuids)
    def getAllContainerUUIDs(self):
        # a list to return
        uuids = []

        # get a list of partitions
        partitionNames = self.getPartitionNames()

        for partition in partitionNames:
            # add the containers in this partition to our list
            uuids = uuids + self.getPartitionContainerUUIDs(partition)

        return uuids

    # Action: check if a container with uuid is running
    #
    # Pre:
    # Post:
    #
    # Params: uuid - the uuid to check
    #
    # Return: boolean - True if running, False otherwise
    def containerIsRunning(self, uuid):
        cmd =  ['jls', '-j', 'trd-' + uuid]
        result = Popen(cmd, stdin=PIPE, stdout=PIPE, stderr=PIPE)

        stdOut, stdErr = result.communicate()

        # exit code of 0 == running
        return (result.returncode == 0)

    # Action: get memory data for this host
    #
    # Pre:
    # Post:
    #
    # Params:
    #
    # Return: dict
    def getMemoryDetails(self, partitionName = None):
        # get memory data
        memCmd = TidyCmd(['top', '-d1'])
        memCmd.appendPipe(['grep', '^Mem:'])
        memOutput = memCmd.run()

        # strip off the "Mem: " part and then split on ", "
        memList = memOutput.split(': ', 1)[-1].split(', ')

        # now turn it into a dict
        memory = {}
        for mem in memList:
            # split each item by the first space
            key = mem.split(' ', 1)[-1].lower()

            # TODO: change value into bytes
            value = mem.split(' ', 1)[0]
            memory[key] = value

        return memory

    # Action: get cpu details for this host
    #
    # Pre:
    # Post:
    #
    # Params:
    #
    # Return: dict
    def getCpuDetails(self, partitionName = None):
        cpu = {}

        # get number of cpus
        numCpuCmd = TidyCmd(['sysctl', '-n', 'hw.ncpu'])
        cpu['num'] = int(numCpuCmd.run())

        # get load average
        uptimeCmd = TidyCmd(['uptime'])
        uptime = uptimeCmd.run()

        # split up the data to get specific values
        loadAverages = uptime.split('load averages: ')[-1]

        cpu['loadAverage'] = {}
        cpu['loadAverage'][1] = float(loadAverages.split(', ')[0])
        cpu['loadAverage'][5] = float(loadAverages.split(', ')[1])
        cpu['loadAverage'][15] = float(loadAverages.split(', ')[2])

        # calculate the available resources over the same time periods
        cpu['availableAverage'] = {}
        cpu['availableAverage'][1] = cpu['num'] - cpu['loadAverage'][1]
        cpu['availableAverage'][5] = cpu['num'] - cpu['loadAverage'][5]
        cpu['availableAverage'][15] = cpu['num'] - cpu['loadAverage'][15]

        # negative values aren't valid
        if (cpu['availableAverage'][1] < 0):
            cpu['availableAverage'][1] = 0
        if (cpu['availableAverage'][5] < 0):
            cpu['availableAverage'][5] = 0
        if (cpu['availableAverage'][15] < 0):
            cpu['availableAverage'][15] = 0

        return cpu

    # Action: get disk details for the given partition
    #
    # Pre:
    # Post:
    #
    # Params:
    #
    # Return: dict
    def getDiskDetails(self, partitionName = None):
        disk = {}

        if (partitionName is None):
            dataset = ZFS_TREDLY_PARTITIONS_DATASET
        else:
            dataset = ZFS_TREDLY_PARTITIONS_DATASET + '/' + partitionName

        # get the partition's free space
        zfs = ZFSDataset(dataset)
        disk['used'] = zfs.getProperty('used')
        disk['available'] = zfs.getProperty('available')

        return disk

    # Action: initialise the zfs datasets ready for use by tredly
    #
    # Pre:
    # Post: default datasets exist
    #
    # Params:
    #
    # Return: boolean - True if success, False otherwise
    def zfsInit(self):
        return False
        '''
        # initialise the zfs datasets ready for use by tredly
        # TODO: this should probably return something meaningful, at the moment it mimics the bash version's behaviour

        zfsTredlyDataset = ZFSDataset(ZFS_TREDLY_DATASET, TREDLY_MOUNT)
        # create it if it doesnt already exist
        if (not zfsTredlyDataset.exists()):
            zfsTredlyDataset.create()

        zfsDownloadsDataset = ZFSDataset(ZFS_TREDLY_DOWNLOADS_DATASET, TREDLY_DOWNLOADS_MOUNT)
        # create it if it doesnt already exist
        if (not zfsDownloadsDataset.exists()):
            zfsDownloadsDataset.create()

        zfsReleasesDataset = ZFSDataset(ZFS_TREDLY_RELEASES_DATASET, TREDLY_RELEASES_MOUNT)
        if (not zfsReleasesDataset.exists()):
            zfsReleasesDataset.create()

        zfsLogDataset = ZFSDataset(ZFS_TREDLY_LOG_DATASET, TREDLY_LOG_MOUNT)
        if (not zfsLogDataset.exists()):
            zfsLogDataset.create()

        zfsPartitionsDataset = ZFSDataset(ZFS_TREDLY_PARTITIONS_DATASET, TREDLY_PARTITIONS_MOUNT)
        if (not zfsLogDataset.exists()):
            zfsLogDataset.create()

        # TODO: create a default partition
        # create a default partition under the partitions dataset
        #if [[ $( zfs list "${ZFS_TREDLY_PARTITIONS_DATASET}/${TREDLY_DEFAULT_PARTITION}" 2> /dev/null | wc -l ) -eq 0 ]]; then
            #partition_create "${TREDLY_DEFAULT_PARTITION}" "" "" "" "" "true"
        #fi
        '''
