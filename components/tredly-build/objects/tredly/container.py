from subprocess import Popen, PIPE

import builtins
from objects.zfs.zfs import ZFSDataset
from objects.ip4.netinterface import NetInterface
from objects.firewall.ipfw import IPFW
from objects.nginx.nginxblock import NginxBlock
from objects.nginx.layer7proxy import *
from tredly.unboundfile import *
from includes.util import *
from includes.defines import *
from includes.output import *
import ipaddress
import time
import os.path
import re
from objects.config.configfile import ConfigFile
from objects.layer4proxy.layer4proxyfile import *
from objects.tredly.tredlyhost import TredlyHost
import pwd
from pprint import pprint

class Container:

    # Constructor
    def __init__(self, partitionName = "default", releaseName = None):
        # pass values
        self.partitionName = partitionName
        self.releaseName = releaseName
        
        # Declare defaults
        self.name = None
        self.hostname = None
        self.group = None
        self.publish = None 
        self.ipv4Whitelist = []
        self.tcpInPorts = []             # list of tcpinports from tredlyfile
        self.tcpOutPorts = []            # list of tcpoutports from tredlyfile
        self.udpInPorts = []             # list of udpinports from tredlyfile
        self.udpOutPorts = []            # list of udpoutports from tredlyfile
        self.dns = []                    # list of dns servers this container uses
        self.layer4Proxy = None
        self.onCreate = []
        self.onStop = []
        self.urls = []                    # list of translated urls from tredlyfile
        self.replicate = None
        self.maxCpu = None
        self.maxHdd = None
        self.maxRam = None
        self.startOrder = None
        self.technicalOptions = []   # this might change to a dict
    
        self.uuid = None                      # UUID of this container
        self.interfaces = []             # list of ip4addr objects
        self.nginxServernameFiles = []        # a list of filenames (not full paths) of nginx server_name files associated with this container. Used for cleanup on destroy.
        self.nginxUpstreamFiles = []          # a list of filenames (not full paths) of nginx upstream files associated with this container. Used for cleanup on destroy.
        self.registeredDNSNames = []     # list of hostnames associated with this container
        self.layer4ProxyTcp = []         # list of tcp ports set up for layer 4 proxy
        self.layer4ProxyUdp = []         # list of udp ports set up for layer 4 proxy
        self.dataset = None
        self.firewall = None                 # firewall object for this container
        self.domainName = None              # domain part of FQDN 
        self.buildEpoch = None              # Time from epoch that container was built
        self.endEpoch = None                # Time since epoch that container finished building
        self.persistentStorageUUID = None   # UUID of persistent storage ZFS dataset
        self.persistentMountpoint = None    # Where persistent storage is mounted
        self.persistentDataset = None       # The dataset of the mounted persistent storage
        
        self.ip6 = None                     # the IP6 data
        self.maxCpu = None                  # maximum cpu available to this container
        self.maxRam = None                  # maximum ram available to this container
        self.maxHdd = None                  # maximum disk space available to container
        self.allowQuotas = None            # allows disk quotas
        self.mountPoint = None              
        self.onStopScript = None            # The location within the container of the script to run on stop
        self.nginxUpstreamDir = None      # The directory on the host where nginx upstream files are kept
        self.nginxServernameDir = None    # The directory on the host where nginx servername files are kept
        self.nginxAccessfileDir = None    # The directory on the host where nginx access files are kept
        self.hostIface = None              # The name of the epair A interface on the host
        self.containerIface = None         # The name of the epair B interface within the container
        self.securelevel = None             # The securelevel that the container is running in
        self.devfsRuleset = None           # devfs ruleset to apply to container
        self.enforceStatfs = None          # Determines what information processes in a jail are able to retrieve about mount points.
        self.childrenMax = None            # The maximum amount of child containers that this container can have
        self.allowSetHostname = None      # Allows a user within the container to set the hostname
        self.allowSysvipc = None           # Allow SysV IPC (inter-process communication) within the container. Necessary for PostgreSQL.
        self.allowRawSockets = None       # Allows the container to create raw sockets. Useful for ping, traceroute etc.
        self.allowChflags = None           # Allows a container to change immutable flags.
        self.allowMount = None             # Allows a container to mount filesystems.
        self.allowMountDevfs = None       # Allows a container to mount devfs filesystems.
        self.allowMountProcfs = None      # Allows a container to mount procfs filesystems.
        self.allowMountTmpfs = None       # Allows a container to mount tmpfs filesystems.
        self.allowMountZfs = None         # Allows a container to mount ZFS filesystems.
        self.allowMountNullfs = None      # Allows a container to mount nullfs filesystems.
        self.allowQuotas = None            # Allows quotas to be applied on container filesystems.
        self.allowSocketAF = None         # Allows access to non standard (IP4, IP6, unix and route) protocol stacks within the container.
        self.execPrestart = None           # Script to run before starting container.
        self.execPoststart = None          # Script to run after starting container.
        self.execPrestop = None            # Script to run before stopping container.
        self.execStop = None               # Script to run when stopping container
        self.execClean = None              # Run commands in a clean environment
        self.execTimeout = None            # Timeout to wait for a command to complete.
        self.execFib = None                # The FIB to use when running commands within a container.
        self.stopTimeout = None            # Timeout to wait for a container to stop.
        
        self.mountDevfs = None
        self.mountFdescfs = None
        self.ip4 = None
        self.ip4SaddrSel = None
        
        self.buildEpoch = None
        self.endEpoch = None
        self.persistentStorageUUID = None
        self.persistentMountpoint = None
        self.persistentDataset = None
        self.allowQuotas = None
        self.mountPoint = None
        
        self.nginxUpstreamDir = None
        self.nginxServernameDir = None
        self.nginxAccessfileDir = None
        self.hostIface = None
        self.containerIface = None
        
        self.hostInterface = None
        self.containerInterfaces = []
            
    def loadFromTredlyfile(self):
        # populate from the Tredlyfile
        self.name = builtins.tredlyFile.json['container']['name']
        self.hostname = builtins.tredlyFile.json['container']['name']
        
        # if the group is set then set it
        if ('group' in builtins.tredlyFile.json['container'].keys()):
            self.group = builtins.tredlyFile.json['container']['group']
        
        
        
        self.publish = builtins.tredlyFile.json['container']['buildOptions']['publish']
        self.tcpInPorts = builtins.tredlyFile.json['container']['firewall']['allowPorts']['tcp']['in']
        self.tcpOutPorts = builtins.tredlyFile.json['container']['firewall']['allowPorts']['tcp']['out']
        self.udpInPorts = builtins.tredlyFile.json['container']['firewall']['allowPorts']['udp']['in']
        self.udpOutPorts = builtins.tredlyFile.json['container']['firewall']['allowPorts']['udp']['out']
        self.ipv4Whitelist = builtins.tredlyFile.json['container']['firewall']['ipv4Whitelist']
        self.layer4Proxy = builtins.tredlyFile.json['container']['proxy']['layer4Proxy']
        self.onCreate = builtins.tredlyFile.json['container']['operations']['onCreate']
        self.onStop = builtins.tredlyFile.json['container']['operations']['onStop']
        self.urls = builtins.tredlyFile.json['container']['proxy']['layer7Proxy']
        self.replicate = builtins.tredlyFile.json['container']['replicate']
        self.startOrder = builtins.tredlyFile.json['container']['startOrder']
        self.technicalOptions = builtins.tredlyFile.json['container']['technicalOptions']
        
        self.maxCpu = builtins.tredlyFile.json['container']['resourceLimits']['maxCpu']
        self.maxRam = builtins.tredlyFile.json['container']['resourceLimits']['maxRam']
        self.maxHdd = builtins.tredlyFile.json['container']['resourceLimits']['maxHdd']
        
        # if dns in tredlyfile is empty then use the internal DNS
        if (len(builtins.tredlyFile.json['container']['customDNS']) == 0):
            self.dns = builtins.tredlyCommonConfig.dns
        else:
            self.dns = builtins.tredlyFile.json['container']['customDNS']
            
        self.onStopScript = None
        
        # domain name = partition name + tld
        self.domainName = self.partitionName + '.' + builtins.tredlyCommonConfig.tld
        
        self.ip4 = CONTAINER_OPTIONS['ip4']
        self.ip4SaddrSel = CONTAINER_OPTIONS['ip4_saddrsel']
        
        # Try to set some variables from the tredlyfile, if it isnt defined then use the default
        try:
            self.securelevel = builtins.tredlyFile.json['container']['technicalOptions']['securelevel']
        except KeyError:
            self.securelevel = CONTAINER_OPTIONS['securelevel']
            
        try:
            self.devfsRuleset = builtins.tredlyFile.json['container']['technicalOptions']['devfs_ruleset']
        except KeyError:
            self.devfsRuleset = CONTAINER_OPTIONS['devfs_ruleset']
            
        try:
            self.enforceStatfs = builtins.tredlyFile.json['container']['technicalOptions']['enforce_statfs']
        except KeyError:
            self.enforceStatfs = CONTAINER_OPTIONS['enforce_statfs']
        
        try:
            self.childrenMax = builtins.tredlyFile.json['container']['technicalOptions']['children.max']
        except KeyError:
            self.childrenMax = CONTAINER_OPTIONS['children.max']
            
        try:
            self.allowSetHostname = builtins.tredlyFile.json['container']['technicalOptions']['allow.set_hostname']
        except KeyError:
            self.allowSetHostname = CONTAINER_OPTIONS['allow.set_hostname']
            
        try:
            self.allowSysvipc = builtins.tredlyFile.json['container']['technicalOptions']['allow.sysvipc']
        except KeyError:
            self.allowSysvipc = CONTAINER_OPTIONS['allow.sysvipc']
            
        try:
            self.allowRawSockets = builtins.tredlyFile.json['container']['technicalOptions']['allow.raw_sockets']
        except KeyError:
            self.allowRawSockets = CONTAINER_OPTIONS['allow.raw_sockets']
            
        try:
            self.allowChflags = builtins.tredlyFile.json['container']['technicalOptions']['allow.chflags']
        except KeyError:
            self.allowChflags = CONTAINER_OPTIONS['allow.chflags']
            
        try:
            self.allowMount = builtins.tredlyFile.json['container']['technicalOptions']['allow.mount']
        except KeyError:
            self.allowMount = CONTAINER_OPTIONS['allow.mount']
            
        try:
            self.allowMountDevfs = builtins.tredlyFile.json['container']['technicalOptions']['allow.mount.devfs']
        except KeyError:
            self.allowMountDevfs = CONTAINER_OPTIONS['allow.mount.devfs']
            
        try:
            self.allowMountDevfs = builtins.tredlyFile.json['container']['technicalOptions']['allow.mount.procfs']
        except KeyError:
            self.allowMountProcfs = CONTAINER_OPTIONS['allow.mount.procfs']
            
        try:
            self.allowMountTmpfs = builtins.tredlyFile.json['container']['technicalOptions']['allow.mount.tmpfs']
        except KeyError:
            self.allowMountTmpfs = CONTAINER_OPTIONS['allow.mount.tmpfs']
            
        try:
            self.allowMountZfs = builtins.tredlyFile.json['container']['technicalOptions']['allow.mount.zfs']
        except KeyError:
            self.allowMountZfs = CONTAINER_OPTIONS['allow.mount.zfs']
            
        try:
            self.allowMountNullfs = builtins.tredlyFile.json['container']['technicalOptions']['allow.mount.nullfs']
        except KeyError:
            self.allowMountNullfs = CONTAINER_OPTIONS['allow.mount.nullfs']
        
        try:
            self.allowQuotas = builtins.tredlyFile.json['container']['technicalOptions']['allow.quotas']
        except KeyError:
            self.allowQuotas = CONTAINER_OPTIONS['allow.quotas']
            
        try:
            self.allowSocketAF = builtins.tredlyFile.json['container']['technicalOptions']['allow.socket_af']
        except KeyError:
            self.allowSocketAF = CONTAINER_OPTIONS['allow.socket_af']
        
        try:
            self.execPrestart = builtins.tredlyFile.json['container']['technicalOptions']['exec.prestart']
        except KeyError:
            self.execPrestart = CONTAINER_OPTIONS['exec.prestart']
        
        try:
            self.execPoststart = builtins.tredlyFile.json['container']['technicalOptions']['exec.poststart']
        except KeyError:
            self.execPoststart = CONTAINER_OPTIONS['exec.poststart']

        try:
            self.execPrestop = builtins.tredlyFile.json['container']['technicalOptions']['exec.prestop']
        except KeyError:
            self.execPrestop = CONTAINER_OPTIONS['exec.prestop']
        
        try:
            self.execStart = builtins.tredlyFile.json['container']['technicalOptions']['exec.start']
        except KeyError:
            self.execStart = CONTAINER_OPTIONS['exec.start']

        try:
            self.execStop = builtins.tredlyFile.json['container']['technicalOptions']['exec.stop']
        except KeyError:
            self.execStop = CONTAINER_OPTIONS['exec.stop']
            
        try:
            self.execClean = builtins.tredlyFile.json['container']['technicalOptions']['exec.clean']
        except KeyError:
            self.execClean = CONTAINER_OPTIONS['exec.clean']
            
        try:
            self.execTimeout = builtins.tredlyFile.json['container']['technicalOptions']['exec.timeout']
        except KeyError:
            self.execTimeout = CONTAINER_OPTIONS['exec.timeout']
            
        try:
            self.execFib = builtins.tredlyFile.json['container']['technicalOptions']['exec.fib']
        except KeyError:
            self.execFib = CONTAINER_OPTIONS['exec.fib']
        
        try:
            self.stopTimeout = builtins.tredlyFile.json['container']['technicalOptions']['stop.timeout']
        except KeyError:
            self.stopTimeout = CONTAINER_OPTIONS['stop.timeout']
        
        try:
            self.mountDevfs = builtins.tredlyFile.json['container']['technicalOptions']['mount.devfs']
        except KeyError:
            self.mountDevfs = CONTAINER_OPTIONS['mount.devfs']
        
        try:
            self.mountFdescfs = builtins.tredlyFile.json['container']['technicalOptions']['mount.fdescfs']
        except KeyError:
            self.mountFdescfs = CONTAINER_OPTIONS['mount.fdescfs']

        return True


    # Action: Create a container within ZFS
    #
    # Pre: 
    # Post: ZFS dataset for container has been created
    #
    # Params: 
    #
    # Return: True if succeeded, False otherwise
    def create(self):
        tredlyHost = TredlyHost()
        
        # generate a UUID for this container
        containerExists = True
        while (containerExists):
            # generate a uuid
            uuid = generateShortUUID(8)
            
            # check if it exists
            containerExists = tredlyHost.containerExists(uuid)
        
        # found an individual uuid so assign it
        self.uuid = uuid
        
        # get the start build time
        self.buildEpoch = int(time.time())
        
        e_note("Creation started at " + time.strftime('%Y-%m-%d %H:%M:%S %z', time.localtime(self.buildEpoch)))
        
        # set some useful vars for use throughout this function
        self.zfsDataset = ZFS_TREDLY_PARTITIONS_DATASET + "/" + self.partitionName + "/" + TREDLY_CONTAINER_DIR_NAME + '/' + self.uuid
        self.mountPoint = TREDLY_PARTITIONS_MOUNT + "/" + self.partitionName + "/" + TREDLY_CONTAINER_DIR_NAME + '/' + self.uuid
        
        # create container dataset
        zfsContainer = ZFSDataset(self.zfsDataset, self.mountPoint)

        # create the dataset
        if (not zfsContainer.create()):
            print("Failed to create container dataset " + self.zfsDataset)
            return False
        
        # mount it
        zfsContainer.mount()
        
        zfsContainer.setProperty(ZFS_PROP_ROOT + ":buildepoch", str(self.buildEpoch))
        
        # create log dir within container
        cmd = ['mkdir', '-p', self.mountPoint + "/" + TREDLY_CONTAINER_LOG_DIR]
        process = Popen(cmd,  stdin=PIPE, stdout=PIPE, stderr=PIPE)
        stdOut, stdErr = process.communicate()
        if (process.returncode != 0):
            e_error("Failed to create container log directory ")

        # combine lists of directories to create
        createDirs = CONTAINER_CREATE_DIRS + CONTAINER_BASEDIRS
        
        # set up some default directories
        for dir in createDirs:
            process = Popen(['mkdir', '-p', self.mountPoint + "/root" + dir],  stdin=PIPE, stdout=PIPE, stderr=PIPE)
            stdOut, stdErr = process.communicate()
            rc = process.returncode
            if (rc != 0):
                e_error("Failed to create container directory " + dir)
                
        # and touch some files
        for file in CONTAINER_CREATE_FILES:
            cmd = ['touch', self.mountPoint + "/root" + file]
            process = Popen(cmd,  stdin=PIPE, stdout=PIPE, stderr=PIPE)
            stdOut, stdErr = process.communicate()
            rc = process.returncode
            if (rc != 0):
                e_error("Failed to create container file " + file)
        
        # copy in some useful directories from the release
        for dir in CONTAINER_COPY_DIRS:
            cmd1 = ['find', "."]
            findCmd = Popen(cmd1, cwd=TREDLY_RELEASES_MOUNT + "/" + self.releaseName + "/root" + dir, stdout=PIPE)
            
            cmd2= ['cpio', '-dp', '--quiet', self.mountPoint + "/root" + dir]
            cpioCmd = Popen(cmd2, cwd=TREDLY_RELEASES_MOUNT + "/" + self.releaseName + "/root" + dir, stdin=findCmd.stdout, stdout=PIPE)
            findCmd.stdout.close()
            stdOut, stdErr = cpioCmd.communicate()
            findCmd.wait()
            
            if (findCmd.returncode != 0) or (cpioCmd.returncode != 0):
                e_error("Failed to copy container directory " + dir)
        
        # copy in some useful files from the host
        for file in CONTAINER_COPY_HOST_FILES:
            # copy in the file if it exists
            if (os.path.isfile(file)):
                process = Popen(['cp', file, self.mountPoint + "/root" + file],  stdin=PIPE, stdout=PIPE, stderr=PIPE)
                stdOut, stdErr = process.communicate()
                if (process.returncode != 0):
                    e_error("Failed to copy container file " + file)

        # write rc.conf
        with open(self.mountPoint + "/root/etc/rc.conf", "w") as rc_conf:
            print('hostname="{}"'.format(self.name), file=rc_conf)
            print('sendmail_enable="NONE"', file=rc_conf)
            print('sendmail_submit_enable="NO"', file=rc_conf)
            print('sendmail_outbound_enable="NO"', file=rc_conf)
            print('sendmail_msp_queue_enable="NO"', file=rc_conf)
            print('syslogd_flags="-c -ss"', file=rc_conf)
            print('firewall_enable="YES"', file=rc_conf)
            print('firewall_script="{}"'.format(IPFW_SCRIPT), file=rc_conf)
            print('firewall_logging="YES"', file=rc_conf)
        
        # write resolv.conf
        with open(self.mountPoint + "/root/etc/resolv.conf", "w") as resolv_conf:
            # if the container has a FQDN then use the rest of it as a search domain
            if (self.domainName is not None):
                print('search ' + self.domainName, file=resolv_conf)
            # print out the dns entries to the container
            for dns in self.dns:
                print('nameserver ' + dns, file=resolv_conf)

        e_note(self.name + " has DNS set to IP(s) " + ", ".join(self.dns))

        # set up the IPFW script with a shebang
        with open(self.mountPoint + "/root" + IPFW_SCRIPT, "w") as ipfw_script:
            print('#!/usr/bin/env sh', file=ipfw_script)
            print('', file=ipfw_script)

            ## mount other filesystems for the container
            # devfs
            cmd = ['mount', '-t', 'devfs', 'devfs', self.mountPoint + '/root/dev']
            process = Popen(cmd,  stdin=PIPE, stdout=PIPE, stderr=PIPE)
            stdOut, stdErr = process.communicate()
            if (process.returncode != 0):
                e_error("Failed to mount devfs")
            
            # tmpfs
            cmd = ['mount', '-t', 'tmpfs', 'tmpfs', self.mountPoint + '/root/tmp']
            process = Popen(cmd,  stdin=PIPE, stdout=PIPE, stderr=PIPE)
            stdOut, stdErr = process.communicate()
            if (process.returncode != 0):
                e_error("Failed to mount tmpfs")


            # set default permissions on /tmp
            cmd = ['chmod', '777', self.mountPoint + '/root/tmp']
            process = Popen(cmd,  stdin=PIPE, stdout=PIPE, stderr=PIPE)
            stdOut, stdErr = process.communicate()
            if (process.returncode != 0):
                e_error("Failed to chmod /tmp")
        
        # set some ZFS properties in the container dataset
        zfsContainer.setProperty(ZFS_PROP_ROOT + ":host_hostuuid", self.uuid)
        zfsContainer.setProperty(ZFS_PROP_ROOT + ":containername", self.name)
        zfsContainer.setProperty(ZFS_PROP_ROOT + ":containergroupname", self.group)
        zfsContainer.setProperty(ZFS_PROP_ROOT + ":partition", self.partitionName)
        zfsContainer.setProperty(ZFS_PROP_ROOT + ":mountpoint", self.mountPoint)
        zfsContainer.setProperty(ZFS_PROP_ROOT + ":maxhdd", self.maxHdd)
        zfsContainer.setProperty(ZFS_PROP_ROOT + ":securelevel", self.securelevel)
        zfsContainer.setProperty(ZFS_PROP_ROOT + ":devfs_ruleset", self.devfsRuleset)
        zfsContainer.setProperty(ZFS_PROP_ROOT + ":enforce_statfs", self.enforceStatfs)
        zfsContainer.setProperty(ZFS_PROP_ROOT + ":children_max", self.childrenMax)
        zfsContainer.setProperty(ZFS_PROP_ROOT + ":allow_set_hostname", self.allowSetHostname)
        zfsContainer.setProperty(ZFS_PROP_ROOT + ":allow_sysvipc", self.allowSysvipc)
        zfsContainer.setProperty(ZFS_PROP_ROOT + ":allow_raw_sockets", self.allowRawSockets)
        zfsContainer.setProperty(ZFS_PROP_ROOT + ":allow_chflags", self.allowChflags)
        zfsContainer.setProperty(ZFS_PROP_ROOT + ":allow_mount", self.allowMount)
        zfsContainer.setProperty(ZFS_PROP_ROOT + ":allow_mount_devfs", self.allowMountDevfs)
        zfsContainer.setProperty(ZFS_PROP_ROOT + ":allow_mount_nullfs", self.allowMountNullfs)
        zfsContainer.setProperty(ZFS_PROP_ROOT + ":allow_mount_procfs", self.allowMountProcfs)
        zfsContainer.setProperty(ZFS_PROP_ROOT + ":allow_mount_tmpfs", self.allowMountTmpfs)
        zfsContainer.setProperty(ZFS_PROP_ROOT + ":allow_mount_zfs", self.allowMountZfs)
        zfsContainer.setProperty(ZFS_PROP_ROOT + ":allow_quotas", self.allowQuotas)
        zfsContainer.setProperty(ZFS_PROP_ROOT + ":allow_socket_af", self.allowSocketAF)
        zfsContainer.setProperty(ZFS_PROP_ROOT + ":exec_prestart", self.execPrestart)
        zfsContainer.setProperty(ZFS_PROP_ROOT + ":exec_poststart", self.execPoststart)
        zfsContainer.setProperty(ZFS_PROP_ROOT + ":exec_prestop", self.execPrestop)
        zfsContainer.setProperty(ZFS_PROP_ROOT + ":exec_start",self.execStart)
        zfsContainer.setProperty(ZFS_PROP_ROOT + ":exec_stop", self.execStop)
        zfsContainer.setProperty(ZFS_PROP_ROOT + ":exec_clean", self.execClean)
        zfsContainer.setProperty(ZFS_PROP_ROOT + ":exec_timeout", self.execTimeout)
        zfsContainer.setProperty(ZFS_PROP_ROOT + ":exec_fib", self.execFib)
        zfsContainer.setProperty(ZFS_PROP_ROOT + ":stop_timeout", self.stopTimeout)
        zfsContainer.setProperty(ZFS_PROP_ROOT + ":mount_devfs", self.mountDevfs)
        zfsContainer.setProperty(ZFS_PROP_ROOT + ":mount_fdescfs", self.mountFdescfs)
        zfsContainer.setProperty(ZFS_PROP_ROOT + ":ip4", self.ip4)
        zfsContainer.setProperty(ZFS_PROP_ROOT + ":ip4_saddrsel", self.ip4SaddrSel)
        zfsContainer.setProperty(ZFS_PROP_ROOT + ":domainname", self.domainName)
        zfsContainer.setProperty(ZFS_PROP_ROOT + ":nginx_accessfile_dir", NGINX_ACCESSFILE_DIR)
        zfsContainer.setProperty(ZFS_PROP_ROOT + ":nginx_servername_dir", NGINX_SERVERNAME_DIR)
        zfsContainer.setProperty(ZFS_PROP_ROOT + ":nginx_upstream_dir", NGINX_UPSTREAM_DIR)
        zfsContainer.setProperty(ZFS_PROP_ROOT + ":releasename", self.releaseName)
        
        # do the ZFS arrays
        for dns in self.dns:
            zfsContainer.appendArray(ZFS_PROP_ROOT + '.dns', dns)
            
        return True


    # Action: populates this object with data from the given dataset
    #
    # Pre: container object exists
    # Post: self has been populated
    #
    # Params: dataset - which dataset to draw the data from
    #
    # Return: True if succeeded, False otherwise
    def loadFromZFS(self, dataset):
        if (dataset is None):
            return False
        self.dataset = dataset
        # get a handle to the dataset
        zfsContainer = ZFSDataset(self.dataset)

        # set the values from zfs - not all zfs values are retrieved here
        self.uuid = zfsContainer.getProperty(ZFS_PROP_ROOT + ":host_hostuuid")
        self.name = zfsContainer.getProperty(ZFS_PROP_ROOT + ":containername")
        self.group = zfsContainer.getProperty(ZFS_PROP_ROOT + ":containergroupname")
        self.partitionName = zfsContainer.getProperty(ZFS_PROP_ROOT + ':partitionname')
        self.mountPoint = zfsContainer.getProperty("mountpoint")
        self.maxHdd = zfsContainer.getProperty(ZFS_PROP_ROOT + ":maxhdd")
        self.securelevel = zfsContainer.getProperty(ZFS_PROP_ROOT + ":securelevel")
        self.devfsRuleset = zfsContainer.getProperty(ZFS_PROP_ROOT + ":devfs_ruleset")
        self.enforceStatfs = zfsContainer.getProperty(ZFS_PROP_ROOT + ":enforce_statfs")
        self.childrenMax = zfsContainer.getProperty(ZFS_PROP_ROOT + ":children_max")
        self.allowSetHostname = zfsContainer.getProperty(ZFS_PROP_ROOT + ":allow_set_hostname")
        self.allowSysvipc = zfsContainer.getProperty(ZFS_PROP_ROOT + ":allow_sysvipc")
        self.allowRawSockets = zfsContainer.getProperty(ZFS_PROP_ROOT + ":allow_raw_sockets")
        self.allowChflags = zfsContainer.getProperty(ZFS_PROP_ROOT + ":allow_chflags")
        self.allowMount = zfsContainer.getProperty(ZFS_PROP_ROOT + ":allow_mount")
        self.allowMountDevfs = zfsContainer.getProperty(ZFS_PROP_ROOT + ":allow_mount_devfs")
        self.allowMountNullfs = zfsContainer.getProperty(ZFS_PROP_ROOT + ":allow_mount_nullfs")
        self.allowMountProcfs = zfsContainer.getProperty(ZFS_PROP_ROOT + ":allow_mount_procfs")
        self.allowMountTmpfs = zfsContainer.getProperty(ZFS_PROP_ROOT + ":allow_mount_tmpfs")
        self.allowMountZfs = zfsContainer.getProperty(ZFS_PROP_ROOT + ":allow_mount_zfs")
        self.allowQuotas = zfsContainer.getProperty(ZFS_PROP_ROOT + ":allow_quotas")
        self.allowSocketAF = zfsContainer.getProperty(ZFS_PROP_ROOT + ":allow_socket_af")
        self.execPrestart = zfsContainer.getProperty(ZFS_PROP_ROOT + ":exec_prestart")
        self.execPoststart = zfsContainer.getProperty(ZFS_PROP_ROOT + ":exec_poststart")
        self.execPrestop = zfsContainer.getProperty(ZFS_PROP_ROOT + ":exec_prestop")
        self.execStart = zfsContainer.getProperty(ZFS_PROP_ROOT + ":exec_start")
        self.execStop = zfsContainer.getProperty(ZFS_PROP_ROOT + ":exec_stop")
        self.execClean = zfsContainer.getProperty(ZFS_PROP_ROOT + ":exec_clean")
        self.execTimeout = zfsContainer.getProperty(ZFS_PROP_ROOT + ":exec_timeout")
        self.execFib = zfsContainer.getProperty(ZFS_PROP_ROOT + ":exec_fib")
        self.stopTimeout = zfsContainer.getProperty(ZFS_PROP_ROOT + ":stop_timeout")
        self.mountDevfs = zfsContainer.getProperty(ZFS_PROP_ROOT + ":mount_devfs")
        self.mountFdescfs = zfsContainer.getProperty(ZFS_PROP_ROOT + ":mount_fdescfs")
        self.ip4 = zfsContainer.getProperty(ZFS_PROP_ROOT + ":ip4")
        self.ip4SaddrSel = zfsContainer.getProperty(ZFS_PROP_ROOT + ":ip4_saddrsel")
        self.domainName = zfsContainer.getProperty(ZFS_PROP_ROOT + ":domainname")
        self.buildEpoch = zfsContainer.getProperty(ZFS_PROP_ROOT + ":buildepoch")
        self.onStopScript = zfsContainer.getProperty(ZFS_PROP_ROOT + ":onstopscript")
        self.hostIface = zfsContainer.getProperty(ZFS_PROP_ROOT + ":host_iface")
        self.releaseName = zfsContainer.getProperty(ZFS_PROP_ROOT + ":releasename")
        self.hostname = self.name
        
        # get the url info to turn into JSON
        urls = zfsContainer.getArray(ZFS_PROP_ROOT + ".url")
        urlCerts = zfsContainer.getArray(ZFS_PROP_ROOT + ".url_cert")
        redirectUrls = zfsContainer.getArray(ZFS_PROP_ROOT + ".redirect_url")
        redirectUrlCerts = zfsContainer.getArray(ZFS_PROP_ROOT + ".redirect_url_cert")
        
        # create json from the zfs urls
        urlArray = []
        for i, value in urls.items():
            # TODO: include the redirects in here
            redirects = []
            
            try:
                urlCert = urlCerts[str(i)]
            except KeyError:
                urlCert = None
            
            urlArray.append({
                'cert': urlCert,
                'maxFileSize': None,
                'redirects': redirects,
                'url': value,
                'websocket': None
            })
        self.urls = urlArray
        
        
        self.layer4ProxyTcp = zfsContainer.getArray(ZFS_PROP_ROOT + ".layer4proxytcp")
        self.layer4ProxyUdp = zfsContainer.getArray(ZFS_PROP_ROOT + ".layer4proxyudp")
        
        # nginx dirs
        self.nginxUpstreamDir = zfsContainer.getProperty(ZFS_PROP_ROOT + ":nginx_upstream_dir")
        self.nginxServernameDir = zfsContainer.getProperty(ZFS_PROP_ROOT + ":nginx_servername_dir")
        self.nginxAccessfileDir = zfsContainer.getProperty(ZFS_PROP_ROOT + ":nginx_accessfile_dir")
        
        # nginx files
        self.nginxUpstreamFiles = zfsContainer.getArray(ZFS_PROP_ROOT + ".nginx_upstream")
        self.nginxServernameFiles = zfsContainer.getArray(ZFS_PROP_ROOT + ".nginx_servername")
        
        # registered dns names
        self.registeredDNSNames = zfsContainer.getArray(ZFS_PROP_ROOT + ".registered_dns_names")

        # get the ip address
        ip4Addr = zfsContainer.getProperty(ZFS_PROP_ROOT + ":ip4_addr")

        # extract its values and create an object
        regex = '^(\w+)\|([\w.]+)\/(\d+)$'
        m = re.match(regex, ip4Addr)
        if (m is not None):
            # create interface object
            iface = NetInterface(m.group(1))
            # add the ip address to this container interface
            iface.ip4Addrs.append(IPv4Interface(m.group(2) + '/' + m.group(3)))

            # add the object to this objects interfaces
            self.containerInterfaces.append(iface)
        
        # set up a firewall object
        self.firewall = IPFW(self.mountPoint + "/root/usr/local/etc", self.uuid)
        
        # read the rules in
        self.firewall.readRules()
        
        
        return True

    # Action: destroy this container
    #
    # Pre: container dataset exists, container may or may not be running
    # Post: container has been stopped and zfs dataset destroyed
    #
    # Params: 
    #
    # Return: True if succeeded, False otherwise
    def destroy(self):
        if (self.dataset is None):
            return False
        
        if (self.uuid is None):
            return False
        
        # dont destroy a running container
        if (self.isRunning()):
            return False

        # get a handle to the dataset
        zfsContainer = ZFSDataset(self.dataset, self.mountPoint)
        
        # unmount all directories EXCEPT devfs mounted into this container
        self.unmountAllDirs()

        # unmount devfs last
        cmd = ['umount', '-f', '-t', 'devfs', self.mountPoint + '/root/dev']
        process = Popen(cmd,  stdin=PIPE, stdout=PIPE, stderr=PIPE)
        stdOut, stdErr = process.communicate()
        if (process.returncode != 0):
            e_error("Failed to unmount devfs")
            print(stdErr)
            
        # destroy the dataset recursively
        return zfsContainer.destroy(True)


    # Action: mount base directories of container
    #
    # Pre: container dataset exists, release exists
    # Post: basedirs have been mounted
    #
    # Params: 
    #
    # Return: True if succeeded, False otherwise
    def mountBaseDirs(self, releaseName = None):
        
        if (releaseName is None):
            releaseName = self.releaseName

        # mount the base directories
        for baseDir in CONTAINER_BASEDIRS:
            params = [
                        'mount', '-t', 'nullfs', '-o', 'ro', TREDLY_RELEASES_MOUNT + "/" + releaseName + "/root" + baseDir, 
                        self.mountPoint + "/root" + baseDir
                    ]
            process = Popen(params,  stdin=PIPE, stdout=PIPE, stderr=PIPE)
            stdOut, stdErr = process.communicate()
            rc = process.returncode
            if (rc != 0):
                e_error("Failed to mount container base directory " + baseDir)

    # Action: unmount just the base directories of container
    #
    # Pre: container dataset exists
    # Post: basedirs have been unmounted
    #
    # Params: 
    #
    # Return: True if succeeded, False otherwise
    def unmountBaseDirs(self):
        # unmount the base directories
        for baseDir in CONTAINER_BASEDIRS:
            cmd =   [ 'umount', self.mountPoint + "/root" + baseDir ]
            process = Popen(cmd,  stdin=PIPE, stdout=PIPE, stderr=PIPE)
            stdOut, stdErr = process.communicate()
            rc = process.returncode
            if (rc != 0):
                e_error("Failed to unmount container base directory " + baseDir)
                print(cmd)

    # check if this container has been started or not
    def isRunning(self):
        # use the jls command to see if this container is running or not
        cmd = ['jls', '-j', 'trd-' + self.uuid, 'jid']
        process = Popen(cmd,  stdin=PIPE, stdout=PIPE, stderr=PIPE)
        stdOut, stdErr = process.communicate()
        
        if (process.returncode == 0):
            return True
        
        return False


    # Action: Start a container
    #
    # Pre: 
    # Post: Container has been started
    #
    # Params: 
    #
    # Return: True if succeeded, False otherwise
    def start(self, bridgeInterface = None, ip4 = None, ip4Cidr = None, ip6 = None, ip6Cidr = None):
        ###################
        # Pre flight Checks
        # check for none values and use defaults instead
        if (bridgeInterface is None):
            # put the container on the private network
            bridgeInterface = builtins.tredlyCommonConfig.lif
            
        if (ip4 is None):
            # get an available ip address for htis network
            ip4 = getAvailableIP4Address(builtins.tredlyCommonConfig.lifNetwork, builtins.tredlyCommonConfig.lifCIDR)
            
        if (ip4Cidr is None):
            # use the default cidr
            ip4Cidr = builtins.tredlyCommonConfig.lifCIDR
            
        if (ip6 is None):
            # set up ip6 address from ip4
            ip6 = ip4ToIP6(ip4)
        
        if (ip6Cidr is None):
        # set up ip6 cidr based off ip4 cidr
            ip6Cidr = str(96 + int(ip4Cidr))
        
        # End Pre flight checks
        ####################
        
        # get an ip4 address object
        ip4Address = IPv4Interface(ip4 + '/' + ip4Cidr)
        
        # get an ip6 address object
        ip6Address = IPv6Interface(ip6 + '/' + ip6Cidr)
        
        # create container interface and generate a mac address for it
        containerInterface = NetInterface()
        containerInterface.generateMac()
        
        # add the ip address to this container interface
        containerInterface.ip4Addrs.append(ip4Address)
        containerInterface.ip6Addrs.append(ip6Address)
        
        
        # mount base dirs before starting
        self.mountBaseDirs()
        
        # get a handle to ZFS properties
        zfsContainer = ZFSDataset(self.zfsDataset, self.mountPoint)
        
        # apply devfs rulesets
        cmd = ['devfs', '-m', self.mountPoint + '/root/dev', 'rule', '-s', self.devfsRuleset, 'applyset']
        process = Popen(cmd,  stdin=PIPE, stdout=PIPE, stderr=PIPE);
        stdOut, stdErr = process.communicate();
        if (process.returncode != 0):
            print("Failed to apply devfs ruleset to container")
        
        # set up a list to go into the command line
        startContainer = [
            "jail",
            "-c",
            "vnet",
            "name=trd-" + self.uuid,
            "host.domainname=" + self.domainName,
            "host.hostname=" + self.name,
            "path=" + self.mountPoint + "/root",
            "securelevel=" + self.securelevel,
            "host.hostuuid=" + self.uuid,
            "devfs_ruleset=" + self.devfsRuleset,
            "enforce_statfs=" + self.enforceStatfs,
            "children.max=" + self.childrenMax,
            "allow.set_hostname=" + self.allowSetHostname,
            "allow.sysvipc=" + self.allowSysvipc,
            "allow.raw_sockets=" + self.allowRawSockets,
            "allow.chflags=" + self.allowChflags,
            "allow.mount=" + self.allowMount,
            "allow.mount.devfs=" + self.allowMountDevfs,
            "allow.mount.nullfs=" + self.allowMountNullfs,
            "allow.mount.procfs=" + self.allowMountProcfs,
            "allow.mount.tmpfs=" + self.allowMountTmpfs,
            "allow.mount.zfs=" + self.allowMountZfs,
            "allow.quotas=" + self.allowQuotas,
            "allow.socket_af=" + self.allowSocketAF,
            "exec.prestart=" + self.execPrestart,
            "exec.poststart=" + self.execPoststart,
            "exec.prestop=" + self.execPrestop,
            "exec.start=" + self.execStart,
            "exec.stop=" + self.execStop,
            "exec.clean=" + self.execClean,
            "exec.timeout=" + self.execTimeout,
            "exec.fib=" + self.execFib,
            "stop.timeout=" + self.stopTimeout,
            "mount.fstab=" + self.mountPoint + "/root/etc/fstab",
            "mount.devfs=" + self.mountDevfs,
            "mount.fdescfs=" + self.mountFdescfs,
            "allow.dying",
            "exec.consolelog=" + self.mountPoint + "/" + TREDLY_CONTAINER_LOG_DIR + "/console",
            "persist"
        ]
        
        # start the container
        process = Popen(startContainer,  stdin=PIPE, stdout=PIPE, stderr=PIPE);
        stdOut, stdErr = process.communicate();
        rc = process.returncode;
        
        # set up the vnet interface
        cmd = ["ifconfig", "epair", "create"]
        process = Popen(cmd,  stdin=PIPE, stdout=PIPE, stderr=PIPE);
        stdOut, stdErr = process.communicate();
        if (process.returncode != 0):
            e_error("Failed to create epair for container")
            print(stdErr)
            
        # strip the newline and assign this variable
        hostInterfaceName = stdOut.rstrip().decode(encoding='UTF-8')
        # swap the a at the end of the string to b
        containerInterface.name =  re.sub('a$', 'b', hostInterfaceName)
        
        # ensure these interfaces exist
        if (not networkInterfaceExists(hostInterfaceName)):
            e_error("Cannot find host interface " + hostInterfaceName)
        if (not networkInterfaceExists(containerInterface.name)):
            e_error("Cannot find container interface " + containerInterfaceName)

        # generate our own mac addresses - vimage has problems with mac collisions
        self.hostInterface = NetInterface(hostInterfaceName)
        self.hostInterface.generateMac()
        
        
        # set the mac addresses for host
        cmd = ["ifconfig", self.hostInterface.name, "ether", self.hostInterface.mac]
        process = Popen(cmd,  stdin=PIPE, stdout=PIPE, stderr=PIPE);
        stdOut, stdErr = process.communicate();
        if (process.returncode != 0):
            e_error("Failed to set host epair " + self.hostInterface.name + "mac address " + self.hostInterface.mac)
            
        # set the mac address for container
        cmd = ["ifconfig", containerInterface.name, "ether", containerInterface.mac]
        process = Popen(cmd,  stdin=PIPE, stdout=PIPE, stderr=PIPE);
        stdOut, stdErr = process.communicate();
        if (process.returncode != 0):
            e_error("Failed to set host epair " + containerInterface.name + "mac address " + containerInterface.mac)
        
        # attach container interface to the container
        cmd = ["ifconfig", containerInterface.name, "vnet", "trd-" + self.uuid]
        process = Popen(cmd,  stdin=PIPE, stdout=PIPE, stderr=PIPE);
        stdOut, stdErr = process.communicate();
        if (process.returncode != 0):
            e_error("Failed to attach epair " + containerInterface.name + " to container trd-" + self.uuid)
        
        # rename the container interface to something more meaningful
        cmd = ["jexec", "trd-" + self.uuid, "ifconfig", containerInterface.name, "name", VNET_CONTAINER_IFACE_NAME]
        process = Popen(cmd,  stdin=PIPE, stdout=PIPE, stderr=PIPE);
        stdOut, stdErr = process.communicate();
        if (process.returncode != 0):
            e_error("Failed to rename container interface")
        
        # change variable name since we just renamed it
        containerInterface.name = VNET_CONTAINER_IFACE_NAME
        
        # link the host interface to the bridge
        cmd = ["ifconfig", bridgeInterface, "addm", self.hostInterface.name, "up"]
        process = Popen(cmd,  stdin=PIPE, stdout=PIPE, stderr=PIPE);
        stdOut, stdErr = process.communicate();
        if (process.returncode != 0):
            e_error("Failed to add host interface to bridge")
        
        
        # indicate that this epair is paired with a container
        cmd = ["ifconfig", self.hostInterface.name, "description", "Connected to container " + self.uuid]
        process = Popen(cmd,  stdin=PIPE, stdout=PIPE, stderr=PIPE);
        stdOut, stdErr = process.communicate();
        if (process.returncode != 0):
            e_error("Failed to set description on host epair")
            
        # bring the host interface up
        cmd = ["ifconfig", self.hostInterface.name, "up"]
        process = Popen(cmd,  stdin=PIPE, stdout=PIPE, stderr=PIPE);
        stdOut, stdErr = process.communicate();
        if (process.returncode != 0):
            e_error("Failed to bring host interface up")
            
        # Set ip4 address
        cmd = ["jexec", "trd-" + self.uuid, "ifconfig", containerInterface.name, "inet", ip4 + "/" + ip4Cidr]
        process = Popen(cmd,  stdin=PIPE, stdout=PIPE, stderr=PIPE);
        stdOut, stdErr = process.communicate();
        if (process.returncode != 0):
            e_error("Failed to set container ip address to " + ip4)
            print(cmd)
            
        # Set ip6 address
        cmd = ["jexec", "trd-" + self.uuid, "ifconfig", containerInterface.name, "inet6", ip6 + "/" + ip6Cidr]
        process = Popen(cmd,  stdin=PIPE, stdout=PIPE, stderr=PIPE);
        stdOut, stdErr = process.communicate();
        if (process.returncode != 0):
            e_error("Failed to set container ip address to " + ip4)
            print(cmd)
        
        # append the container interface
        self.containerInterfaces.append(containerInterface)
        
        e_note(self.name + " allocated IP " + ip4)
        
        # set the ip4 address in zfs
        zfsContainer.setProperty(ZFS_PROP_ROOT + ":ip4_addr", bridgeInterface + "|" + ip4 + "/" + ip4Cidr)
        
        # set the ip6 address in zfs
        zfsContainer.setProperty(ZFS_PROP_ROOT + ":ip6_addr", bridgeInterface + "|" + ip6 + "/" + ip6Cidr)
        
        
        # and the interface names
        zfsContainer.setProperty(ZFS_PROP_ROOT + ":host_iface", self.hostInterface.name)
        zfsContainer.setProperty(ZFS_PROP_ROOT + ":container_iface", containerInterface.name)
        
        # get a handle to the hosts ipfw setup
        hostFirewall = IPFW('/usr/local/etc')
        hostFirewall.readRules()
        # set up some further routing for containers
        if (bridgeInterface == builtins.tredlyCommonConfig.wif):
            # this is a public container 

            # get the wan iface's ip address
            wanIP = getInterfaceIP4(builtins.tredlyCommonConfig.wifPhysical)
            
            # add a route to the private network
            cmd = ["jexec", "trd-" + self.uuid, "route", "add", "-net", builtins.tredlyCommonConfig.lifNetwork + "/" + builtins.tredlyCommonConfig.lifCIDR, wanIP]
            process = Popen(cmd,  stdin=PIPE, stdout=PIPE, stderr=PIPE)
            stdOut, stdErr = process.communicate();
            if (process.returncode != 0):
                e_error("Failed to add route from public to private network")
                print(cmd)
                
            # get the current default route
            f = os.popen("netstat -r4n | grep default | awk '{print $2}'" )
            defaultRoute = f.read()
            
            # Add this ip address to the IPFW public ip table
            hostFirewall.appendTable(1, ip4)
            # Add the host's epair to the ipfw public epair table
            hostFirewall.appendTable(2, self.hostInterface.name)
            
            hostFirewall.apply()
        else:
            # private container, default comes from config
            defaultRoute = builtins.tredlyCommonConfig.vnetDefaultRoute
            
        # now set hte default route
        cmd = ["jexec", "trd-" + self.uuid, "route", "add", "default", defaultRoute]
        process = Popen(cmd,  stdin=PIPE, stdout=PIPE, stderr=PIPE);
        stdOut, stdErr = process.communicate();
        if (process.returncode != 0):
            e_error("Failed to add default route")
            print(cmd)
        
        
        # set resource limits
        self.applyResourceLimits()
        
        # apply firewall rules
        e_note("Configuring firewall for " + self.name)
        if (self.addContainerFirewallRules()):
            e_success("Success")
        else:
            e_error("Failed")

        # run the on create commands
        self.runOnCreateCmds()

        # create the onstop script
        self.createOnStopScript()
        
        # set up the container's hostname in DNS
        e_note("Adding container to DNS")
        
        # Set the container's hostname up in unbound
        unboundFile = UnboundFile(UNBOUND_CONFIG_DIR + "/" + unboundFormatFilename(self.domainName))
        # read contents
        unboundFile.read()
        
        # only assign this hostname to the first interface
        if (unboundFile.append("local-data", self.hostname + '.' + self.domainName, "IN", "A", str(self.containerInterfaces[0].ip4Addrs[0].ip), self.uuid)):
            zfsContainer.appendArray(ZFS_PROP_ROOT + ".registered_dns_names", self.hostname + '.' + self.domainName)
        
        # write out the file and show message to user
        if (unboundFile.write()):
            e_success("Success")
        else:
            e_error("Failed")
        
        return True

    # stops this container
    def stop(self):
        if (self.isRunning()):
            # check if an onstop script is set and if so, run it
            if (self.onStopScript is not None) and (self.onStopScript != '-'):
                e_note("Running onStop script")
                if (self.runCmd('sh -c "' + self.onStopScript + '"')):
                    e_success("Success")
                else:
                    e_error("Failed")
        
        
            e_note("Stopping Container " + self.name)
            cmd = ['jail', '-r', 'trd-' + self.uuid]
            process = Popen(cmd,  stdin=PIPE, stdout=PIPE, stderr=PIPE)
            stdOut, stdErr = process.communicate()
            
            if (process.returncode == 0):
                e_success("Success")
            else:
                e_error("Failed")

        # check if this container is on the public interface
        if (len(self.containerInterfaces) > 0):
            if (self.containerInterfaces[0].name == builtins.tredlyCommonConfig.wif):
                # it is so remove our elements from the ipfw tables
                # get a ipfw object on the host
                hostFirewall = IPFW('/usr/local/etc')
                hostFirewall.readRules()
                
                # remove the ip from table 1
                if (not hostFirewall.removeFromTable(1, str(self.containerInterfaces[0].ip4Addrs[0].ip))):
                    e_error("Failed to remove ip address from host table 1")
                
                # remove the epair from table 2
                if (not hostFirewall.removeFromTable(2, self.containerInterfaces[0].name)):
                    e_error("Failed to remove interface from host table 2")
                
                hostFirewall.apply()

        # tear down any resource limits if they were placed
        if (self.maxCpu is not None) or (self.maxRam is not None):
            e_note("Removing resource limits")
            cmd = ['rctl', '-r', 'jail:trd-' + self.uuid]
            process = Popen(cmd,  stdin=PIPE, stdout=PIPE, stderr=PIPE)
            stdOut, stdErr = process.communicate()
            
            if (process.returncode == 0):
                e_success("Success")
            else:
                e_error("Failed")
                

        # make sure the hosts epair exists before attempting to destroy it
        if (networkInterfaceExists(self.hostIface)):
            e_note("Removing container networking")
            
            cmd = [ 'ifconfig', self.hostIface, 'destroy']
            process = Popen(cmd,  stdin=PIPE, stdout=PIPE, stderr=PIPE)
            stdOut, stdErr = process.communicate()
            rc = process.returncode
            if (rc == 0):
                e_success("Success")
            else:
                e_error("Failed to remove epair " + self.hostIfaced)

        return True

    # Action: set up firewall rules on a container
    #
    # Pre: container exists and is running
    # Post: ipfw rules have been added to container
    #
    # Params: 
    #
    # Return: True if succeeded, False otherwise
    def addContainerFirewallRules(self):
        # Set up the firewall rules for this container
        self.firewall = IPFW(self.mountPoint + "/root/usr/local/etc", self.uuid)
        
        # include the rules for whitelists even if the tables are empty
        # the table will be updated instead of the ruleset whenever the whitelist changes
        
        # loop over the interfaces
        for containerInterface in self.containerInterfaces:
            # and the ips assigned to this interface
            for containerIP4 in containerInterface.ip4Addrs:
                # containergroup members
                self.firewall.openPort("in", "tcp", containerInterface.name, "'table(1)'", str(containerIP4), self.tcpInPorts)
                self.firewall.openPort("in", "udp", containerInterface.name, "'table(1)'", str(containerIP4), self.udpInPorts)
                
                # Partition whitelist rules
                self.firewall.openPort("in", "tcp", containerInterface.name, "'table(2)'", str(containerIP4), self.tcpInPorts)
                self.firewall.openPort("in", "udp", containerInterface.name, "'table(2)'", str(containerIP4), self.udpInPorts)
                
                # Container whitelist
                self.firewall.openPort("in", "tcp", containerInterface.name, "'table(3)'", str(containerIP4), self.tcpInPorts)
                self.firewall.openPort("in", "udp", containerInterface.name, "'table(3)'", str(containerIP4), self.udpInPorts)
                
                
                # Add some default rules for this interface if it isnt in a containergorup and doesnt have whitelist set
                if (self.group is None) and (self.ipv4Whitelist is None):
                    # open the IN ports from any
                    self.firewall.openPort("in", "tcp", containerInterface.name, "any", str(containerIP4), self.tcpInPorts)
                    self.firewall.openPort("in", "udp", containerInterface.name, "any", str(containerIP4), self.udpInPorts)

                # if user didn't request "any" out for tcp, then allow 80 (http), and 443 (https) out by default
                if (not "any" in self.tcpOutPorts):
                    self.firewall.openPort("out", "tcp", containerInterface.name, str(containerIP4), "any", [80])
                    self.firewall.openPort("out", "tcp", containerInterface.name, str(containerIP4), "any", [443])
                    
                # if user didn't request "any" out for udp, then allow 53 (dns) out by default
                if (not "any" in self.udpOutPorts):
                    self.firewall.openPort("out", "udp", containerInterface.name, str(containerIP4), "any", [53])
                
                # open port 80 if a urlcert is blank, and open port 443 if a urlcert is not blank
                openPort443 = False
                openPort80 = False
                for url in self.urls:
                    if (url['cert'] is None):
                        openPort80 = True
                    elif (url['cert'] is not None):
                        openPort443 = True
                        
                if (openPort80):
                    self.firewall.openPort("in", "tcp", containerInterface.name, builtins.tredlyCommonConfig.httpProxyIP, str(containerIP4), [80])
                if (openPort443):
                    self.firewall.openPort("in", "tcp", containerInterface.name, builtins.tredlyCommonConfig.httpProxyIP, str(containerIP4), [443])
                
                # allow out ports as specified
                self.firewall.openPort("out", "tcp", containerInterface.name, str(containerIP4), "any", self.tcpOutPorts)
                self.firewall.openPort("out", "udp", containerInterface.name, str(containerIP4), "any", self.udpOutPorts)
                
                # allow DNS to the proxy
                self.firewall.openPort("out", "udp", containerInterface.name, str(containerIP4), builtins.tredlyCommonConfig.httpProxyIP, [53])
                
                # allow this container to talk to itself on any port on this interface
                self.firewall.openPort("any", "ip", containerInterface.name, str(containerIP4), str(containerIP4), ["any"])
                
        # and allow this container to talk to itself on loopback
        self.firewall.openPort("any", "ip", "lo0", "any", "any", ["any"])
        
        # set the container whitelist table up in this container
        for ip4 in self.ipv4Whitelist:
            self.firewall.appendTable(3, ip4)

            
        # Set the partition whitelist table up in this new container
        zfsPartition = ZFSDataset('zroot/tredly/ptn/' + self.partitionName)
        
        # get the whitelist
        ptnWhitelist = zfsPartition.getArray(ZFS_PROP_ROOT + '.ptn_ip4whitelist')

        for key, ip4 in ptnWhitelist.items():
            self.firewall.appendTable(2, ip4)
        
        # get a handle to ZFS properties
        zfsContainer = ZFSDataset(self.zfsDataset, self.mountPoint)
        # register ports in ZFS
        for tcpInPort in self.tcpInPorts:
            zfsContainer.appendArray(ZFS_PROP_ROOT + ".tcpinports", str(tcpInPort))
        for udpInPort in self.udpInPorts:
            zfsContainer.appendArray(ZFS_PROP_ROOT + ".udpinports", str(udpInPort))
        for tcpOutPort in self.tcpOutPorts:
            zfsContainer.appendArray(ZFS_PROP_ROOT + ".tcpoutports", str(tcpOutPort))
        for udpOutPort in self.udpOutPorts:
            zfsContainer.appendArray(ZFS_PROP_ROOT + ".udpoutports", str(udpOutPort))
        
        # apply the rules and return
        return self.firewall.apply()
    
    # apply resource limits to this container
    def applyResourceLimits(self):
        # set max ram
        if (self.maxRam != 'unlimited'):
            cmd = ['rctl', '-a', 'jail:trd-' + self.uuid + ":memoryuse:deny=" + self.maxRam]
            process = Popen(cmd,  stdin=PIPE, stdout=PIPE, stderr=PIPE)
            stdOut, stdErr = process.communicate()
            if (process.returncode != 0):
                e_error("Failed to set maxRam on container " + self.name)
                return False
            else:
                e_warning("maxRam property value was set. Setting to " + self.maxRam + "GB")
        else:
            e_warning("maxRam property value was not set. Defaulting to unlimited.")
        
        # set max cpu
        if (self.maxCpu != 'unlimited'):
            cmd = ['rctl', '-a', 'jail:trd-' + self.uuid + ":pcpu:deny=" + self.maxCpu.rstrip('%')]
            process = Popen(cmd,  stdin=PIPE, stdout=PIPE, stderr=PIPE)
            stdOut, stdErr = process.communicate()
            if (process.returncode != 0):
                e_error("Failed to set maxCpu on container " + self.name)
                print(cmd)
                return False
            else:
                e_warning("maxCpu property value was set. Setting to " + self.maxCpu.rstrip('%') + "%")
        else:
            e_warning("maxCpu property value was not set. Defaulting to unlimited.")

        # set quota on ZFS (maxHdd)
        if (self.maxHdd != 'unlimited'):
            zfsContainer = ZFSDataset(self.zfsDataset, self.mountPoint)
            
            if (not zfsContainer.setProperty("quota", self.maxHdd)):
                e_error("Failed to set maxHdd on container " + self.name)
            else:
                e_warning("maxHdd property value was set. Setting to " + self.maxHdd + "GB")
        else:
            e_warning("maxHdd property value was not set. Defaulting to unlimited.")
        return True
    
    
    def runOnCreateCmds(self):
        # loop over the create commands
        for createCmd in self.onCreate:
            if (createCmd['type'] == "exec"):    # ONSTART COMMANDS
                e_note('Running onStart command: "' +  createCmd['value'] +'"')
                
                # run it
                if (self.runCmd(createCmd['value'])):
                    e_success("Success")
                else:
                    e_error("Failed")
            
            elif (createCmd['type'] == "installPackage"):   # INSTALL PACKAGE COMMANDS
                e_note("Installing: " + createCmd['value'] + " and its dependencies")
                
                # first mount the pkg cache from the host
                cmd = ['mount_nullfs', '/var/cache/pkg', self.mountPoint + '/root/var/cache/pkg']
                process = Popen(cmd,  stdin=PIPE, stdout=PIPE, stderr=PIPE)
                stdOut, stdErr = process.communicate()
                if (process.returncode != 0):
                    e_error("Failed to mount host's pkg cache")
                
                # proceed with install from the host
                cmd = ['pkg', '-j', 'trd-' + self.uuid, 'install', "-y", createCmd['value']]
                
                installProcess = Popen(cmd,  stdin=PIPE, stdout=PIPE, stderr=PIPE)
                stdOut, stdErr = installProcess.communicate()
                if (installProcess.returncode != 0):
                    # errored
                    print(str(stdErr))
                    e_error("Failed")
                else:
                    e_success("Success")
                    
                # now unmount it
                cmd = ['umount', self.mountPoint + '/root/var/cache/pkg']
                process = Popen(cmd,  stdin=PIPE, stdout=PIPE, stderr=PIPE)
                stdOut, stdErr = process.communicate()
                if (process.returncode != 0):
                    e_error("Failed to unmount host's pkg cache")
                    
                # if the install succeeded and this was a postgres server then do workarounds
                if (installProcess.returncode == 0) and (re.match('^.*postgresql[0-9]*-server.*$', createCmd['value'])):
                    self.applyPostgresWorkaroundOnStart()
                
            elif (createCmd['type'] == "fileFolderMapping"):
                # if first word of the source is "partition" then the file comes from the partition
                if (re.match('^partition/', createCmd['source'])):
                    e_note('Copying Partition Data "' + createCmd['source'] + '" to ' + createCmd['target'])
                    
                    # create the path to the source file/directory
                    source = TREDLY_PARTITIONS_MOUNT + "/" + self.partitionName + "/" + TREDLY_PTN_DATA_DIR_NAME + "/" + createCmd['source'].lstrip('partition/').rstrip('/') + '/'
                else:
                    e_note('Copying Container Data "' + createCmd['source'] + '" to ' + createCmd['target'])
                    
                    # create the path to the source file/directory
                    source = builtins.tredlyFile.fileLocation + createCmd['source']
                    
                # set up the target
                target = self.mountPoint + '/root' + createCmd['target']
                targetDir = os.path.dirname(target)

                # make sure the target exists
                if (not os.path.isdir(targetDir)):
                    os.makedirs(targetDir)
                
                # Copy the data in
                cmd = ['cp', '-R', source, target]

                process = Popen(cmd,  stdin=PIPE, stdout=PIPE, stderr=PIPE)
                stdOut, stdErr = process.communicate()
                if (process.returncode != 0):
                    # errored
                    e_error("Failed to copy " + source + " to " + createCmd['target'])
                    print(stdErr)
                else:
                    # Success
                    e_success("Success")
                    
            elif (createCmd['type'] == 'persistentStorage'):
                # TODO
                e_error("Persistent storage yet to be implemented")
            else:
                e_warning("Unknown command " + createCmd['type'])
    
    # run a command within this container
    def runCmd(self, command):
        
        # split it up so we can pass to popen
        #cmd = command.split()
        
        # add a jexec before the command passed to us
        command = "jexec trd-" + self.uuid + ' sh -c "' + command + '"'
        # TODO: move oncreate commands to an oncreate script, remove shell=true below as it is a security risk. note that this behaviour allows shell injection in the same way as the bash version. This needs a fix once we move away from bash building
        process = Popen(command,  stdin=PIPE, stdout=PIPE, stderr=PIPE, shell=True)
        stdOut, stdErr = process.communicate()
        if (process.returncode != 0):
            # errored
            print(str(stdErr))
            return False
        
        return True
    
    def createOnStopScript(self):
        # set the onstop script location
        self.onStopScript = "/etc/rc.onstop"
        
        e_note("Creating onStop script")
        
        # open the onstop script and write in the commands
        with open(self.mountPoint + '/root' + self.onStopScript, "w") as onstop_script:
            # put the shebang into the file
            print("#!/usr/bin/env sh", file=onstop_script)
            
            # loop over the create commands
            for stopCmd in self.onStop:
                if (stopCmd['type'] == "exec"):
                    # put the command into the onstop file
                    print(stopCmd['value'], file=onstop_script)
                else:
                    print("Unknown command " + stopCmd['type'])
        
        # set the file's permissions
        os.chmod(self.mountPoint + '/root' + self.onStopScript, 0o700)
        
        # place onstopscript into ZFS
        zfsContainer = ZFSDataset(self.zfsDataset, self.mountPoint)
        zfsContainer.setProperty(ZFS_PROP_ROOT + ":onstopscript", self.onStopScript)
        
        e_success("Success")
        
    
    # applies the postgres workaround to this container
    def applyPostgresWorkaroundOnStart(self):
        
        e_note("This container uses postgresql, changing the pgsql UID within this container")
        
        # a variable for looping
        userExists = True

        # use the last 2 parts of the ip address as the new uid for postgres
        ipPart3 = str(self.containerInterfaces[0].ip4Addrs[0].ip).split('.')[-2]
        ipPart4 = str(self.containerInterfaces[0].ip4Addrs[0].ip).split('.')[-1]
        
        newUID = int("70" + ipPart3 + ipPart4)
        
        # check if this uid already exists
        while (userExists):
            try:
                # check if user exists
                pwd.getpwuid(newUID)
            except KeyError:
                # Handle non existent user
                userExists = False
            else:
                # Handle existing user
                newUID = newUID + 1
                userExists = True
        
        # modify the uid within the container
        cmd = ['jexec', 'trd-' + self.uuid, '/usr/sbin/pw', 'usermod', 'pgsql', '-u', str(newUID)]
        process = Popen(cmd,  stdin=PIPE, stdout=PIPE, stderr=PIPE)
        stdOut, stdErr = process.communicate()
        if (process.returncode == 0):
            e_success("Success")
        else:
            e_error("Failed")
            print(cmd)
            print(stdErr)
            return False
        
        e_note("Changing UID of files owned by pgsql")
        # change the ownership of all files with owner uid 70
        #eval "jexec ${jid} sh -c 'find / -user 70 -exec chown -h pgsql {} \;'"
        cmd = ['jexec', 'trd-' + self.uuid, 'find', '/', '-user', '70', '-exec', 'chown', '-h', 'pgsql', '{}', ';']
        process = Popen(cmd,  stdin=PIPE, stdout=PIPE, stderr=PIPE)
        stdOut, stdErr = process.communicate()
        if (process.returncode == 0):
            e_success("Success")
        else:
            e_error("Failed")
            print(cmd)
            print(stdErr)
            return False
    
        return True
    # applies the postgres workaround to this container
    def applyPostgresWorkaroundOnStop(self):
        e_note("Shutting down and cleaning up postgresql")
        
        # stop postgres server
        if (self.runCmd("/usr/sbin/service postgresql stop")):
            e_success("Success")
        else:
            e_error("Failed")
    
    # registers any urls in layer 7 proxy that this container responds to
    def registerURLs(self):
        # TODO: recycle this code for reuse into the layer7proxy object
        
        e_note('Configuring layer 7 Proxy (HTTP) for ' + self.name)
        # set up ZFS access to container dataset
        zfsContainer = ZFSDataset(self.zfsDataset, self.mountPoint)
        
        layer7Proxy = Layer7Proxy()
        
        urlIncludes = []
        
        # check if a whitelist exists and whitelist each url
        if (len(self.ipv4Whitelist) > 0):
            urlIncludes.append('/usr/local/etc/nginx/access/' + nginxFormatFilename(self.uuid))
        
        # get the partition whitelist
        zfsPartition = ZFSDataset('zroot/tredly/ptn/' + self.partitionName)
        ptnWhitelist = zfsPartition.getArray(ZFS_PROP_ROOT + '.ptn_ip4whitelist')
        # include the ptn whitelist if it has elements
        if (len(ptnWhitelist) > 0):
            urlIncludes.append('/usr/local/etc/nginx/access/ptn_' + nginxFormatFilename(self.partitionName))
        
        for urlObj in self.urls:
            # Set some values for http/https
            if (urlObj['cert'] is not None):
                sslCert = "ssl/" + self.partitionName + "/" + urlObj['cert'].split('/')[-1] + "/server.crt"
                sslKey = "ssl/" + self.partitionName + "/" + urlObj['cert'].split('/')[-1] + "/server.key"
                protocol = 'https'
            else:
                sslCert = None
                sslKey = None
                protocol = 'http'

            # split up the domain and directory parts of the url
            if ('/' in urlObj['url'].rstrip('/')):
                urlDomain = urlObj['url'].split('/', 1)[0]
                urlDirectory = '/' + urlObj['url'].split('/', 1)[1]
            else:
                urlDomain = urlObj['url']
                urlDirectory = '/'
                
            # set up the filenames
            servernameFilename = protocol + '-' + nginxFormatFilename(urlDomain.rstrip('/'))
            upstreamFilename = protocol + '-' + nginxFormatFilename(urlObj['url'].rstrip('/'))

            # register this URL
            if (layer7Proxy.registerUrl(urlObj['url'], str(self.containerInterfaces[0].ip4Addrs[0].ip), urlObj['maxFileSize'], urlObj['enableWebsocket'], servernameFilename, upstreamFilename, sslCert, sslKey, urlIncludes)):
                # register the URL in ZFS
                zfsContainer.appendArray(ZFS_PROP_ROOT + ".url", urlObj['url'])
                
                # if a cert was used then register that too
                if (sslCert is not None):
                    zfsContainer.appendArray(ZFS_PROP_ROOT + ".url_cert", urlObj['cert'].split('/')[-1])
                
                # register the filenames in ZFS for destruction
                zfsContainer.appendArray(ZFS_PROP_ROOT + ".nginx_upstream", upstreamFilename)
                zfsContainer.appendArray(ZFS_PROP_ROOT + ".nginx_servername", servernameFilename)
            else:
                e_error("Failed to register url " + urlObj['url'])

            # add container whitelist
            if (len(self.ipv4Whitelist) > 0):
                layer7Proxy.registerAccessFile('/usr/local/etc/nginx/access/' + self.uuid, self.ipv4Whitelist, True)

            # set the partition whitelist access file
            if (len(ptnWhitelist) > 0):
                layer7Proxy.registerAccessFile('/usr/local/etc/nginx/access/ptn_' + self.partitionName, ptnWhitelist.values(), True)
            
            
            # Register this URL in DNS
            e_note("Registering " + urlDomain + " in DNS")

            # and the object
            unboundFile = UnboundFile(UNBOUND_CONFIG_DIR + "/" + unboundFormatFilename(urlDomain))
            # read contents
            unboundFile.read()
            
            # assign the url domain to the proxy IP in dns
            if (unboundFile.append("local-data", urlDomain, "IN", "A", builtins.tredlyCommonConfig.httpProxyIP, self.uuid)):
                # register the url within zfs
                zfsContainer.appendArray(ZFS_PROP_ROOT + ".registered_dns_names", urlDomain)
            
            # write out the file and show message to user
            if (unboundFile.write()):
                e_success("Success")
            else:
                e_error("Failed")
                
            # check if a cert wqs issued for the url, and if so then create a http redirect
            if (sslCert is not None):
                if (layer7Proxy.registerUrlRedirect(urlObj['url'], 'https://' + urlObj['url'])):
                    # register the redirect url within zfs
                    zfsContainer.appendArray(ZFS_PROP_ROOT + ".redirect_url", 'http://' + urlObj['url'])
                else:
                    e_error("Failed to register HTTP to HTTPS redirect for " + urlObj['url'])

            # set up Redirects
            redirectTo = urlObj['url']
            for redirectFrom in urlObj['redirects']:
                redirectFromDomain = redirectFrom['url'].split('://')[-1]
                
                # set the paths if the cert is set
                if (redirectFrom['cert'] is not None):
                    sslCert = 'ssl/' + self.partitionName + '/' + redirectFrom['cert'].split('/')[-1] + '/server.crt'
                    sslKey = 'ssl/' + self.partitionName + '/' + redirectFrom['cert'].split('/')[-1] + '/server.key'
                    redirectFromProtocol = "https"
                else:
                    sslCert = None
                    sslKey = None
                    redirectFromProtocol = "http"
                
                # register the redirect
                if (layer7Proxy.registerUrlRedirect(redirectFromDomain, redirectTo, sslCert, sslKey)):
                    # register the redirect url within zfs
                    zfsContainer.appendArray(ZFS_PROP_ROOT + ".redirect_url", redirectFrom['url'])
                else:
                    e_error("Failed to register redirect from " + redirectFrom['url'] + " to " + urlObj['url'])
                
                # Register this URL in DNS
                e_note("Registering " + redirectFrom['url'] + " in DNS")
                # base DNS filename off last 3 (sub)domains
                fileParts = redirectFrom['url'].split('://')[1].split('.')
                # create the filename
                filename = fileParts[-3] + '.' + fileParts[-2] + '.' + fileParts[-1]
                # and the object
                unboundFile = UnboundFile(UNBOUND_CONFIG_DIR + "/" + unboundFormatFilename(filename))
                # read contents
                unboundFile.read()
                
                # only assign this hostname to the first interface
                if (unboundFile.append("local-data", redirectFrom['url'].split('://')[1], "IN", "A", builtins.tredlyCommonConfig.httpProxyIP, self.uuid)):
                    # success so include this url in zfs
                    zfsContainer.appendArray(ZFS_PROP_ROOT + ".registered_dns_names", redirectFrom['url'])
                
                # write out the file and show message to user
                if (unboundFile.write()):
                    e_success("Success")
                else:
                    e_error("Failed")

        if (layer7Proxy.reload()):
            e_success("Success")
        else:
            e_error("Failed")
    
    # sets itself up in the layer 4 proxy config
    def registerLayer4Proxy(self):
        # get a handle to ZFS
        zfsContainer = ZFSDataset(self.zfsDataset, self.mountPoint)

        # set up layer 4 proxy if it was requested
        if (self.layer4Proxy):
            layer4Proxy = Layer4ProxyFile(IPFW_FORWARDS)
            # read the file
            layer4Proxy.read()
            
            # add tcp ports
            for tcpInPort in self.tcpInPorts:
                # add the rule
                if (layer4Proxy.append(self.uuid, 'tcp', tcpInPort, str(self.containerInterfaces[0].ip4Addrs[0].ip), str(tcpInPort))):
                    # it worked, so append zfs 
                    zfsContainer.appendArray(ZFS_PROP_ROOT + ".layer4proxytcp", str(self.containerInterfaces[0].ip4Addrs[0].ip) + ":" + str(tcpInPort))
                else:
                    e_error("Could not add port " + str(tcpInPort) + "tcp to Layer 4 Proxy")
    
            # add udp ports
            for udpInPort in self.udpInPorts:
                # add the rule
                if (layer4Proxy.append(self.uuid, 'udp', udpInPort, str(self.containerInterfaces[0].ip4Addrs[0].ip), str(udpInPort))):
                    # it worked, so append zfs 
                    zfsContainer.appendArray(ZFS_PROP_ROOT + ".layer4proxyudp", str(self.containerInterfaces[0].ip4Addrs[0].ip) + ":" + str(udpInPort))
                else:
                    e_error("Could not add port " + str(udpInPort) + "udp to Layer 4 Proxy")
    
            # write out the layer 4 proxy file and run it if it succeeded, returning hte value
            if (layer4Proxy.write()):
                return layer4Proxy.reload()

    # returns all mounts used by this container in a list EXCEPT devfs
    def getMounts(self):
        # a list to return
        mounts = []

        # list the mounts
        process = Popen(['mount'], stdin=PIPE, stdout=PIPE, stderr=PIPE)
        
        stdOut, stdErr = process.communicate()
        if (process.returncode != 0):
            return None
    
        stdOutString = stdOut.decode("utf-8")
        
        for line in stdOutString.splitlines():
            # look for this containers mountpoints
            if (re.match('^' + self.mountPoint.rstrip('/') + '/', line.split()[2])):
                # make sure its not a devfs line
                if (line.split()[0] != 'devfs'):
                    # found a line for this container
                    mounts.append(line.split()[2])
                
        
        return mounts

    # unmounts all directories of a container that are currently mounted (minus devfs)
    def unmountAllDirs(self):
        # get a list of mounts to unmount
        mounts = self.getMounts()
        
        returnValue = True
        
        # unmount the directories
        for mount in mounts:
            cmd = ['umount', '-f', mount]
            process = Popen(cmd,  stdin=PIPE, stdout=PIPE, stderr=PIPE)
            stdOut, stdErr = process.communicate()
            rc = process.returncode
            if (rc != 0):
                e_error("Failed to unmount container directory " + baseDir)
                print(cmd)
                
                returnValue = (False and returnValue)
            else:
                returnValue = (True and returnValue)
        
        return returnValue