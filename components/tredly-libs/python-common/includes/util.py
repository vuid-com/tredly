# utilities useful to Tredly
import string
import random
from ipaddress import *
from includes.defines import *
from includes.output import *
import os.path
from objects.zfs.zfs import ZFSDataset
import __main__
import builtins
import re
from urllib.request import urlopen
from subprocess import Popen, PIPE

# looks for a tredlyfile at the given path and returns the full path to the tredlyfile
# if none found, None is returned
def findTredlyFile(path):
    # strip trailing slash from path
    path = path.rstrip('/')

    # make sure dir exists
    if (not os.path.isdir(path)):
        return None

    # look for supported tredly files
    if (os.path.isfile(path + "/tredly.yaml")):    # look for tredly.yaml
        return(path + "/tredly.yaml")
    elif (os.path.isfile(path + "/Tredlyfile")):   # look for flat file Tredlyfile
        return(path + "/Tredlyfile")
    elif (os.path.isfile(path + "/tredly.json")):    # look for tredly.json
        return(path + "/tredly.json")

    return None

# copies files or folders from a given source to destination
# handles /path/to/folder and partition/path/to/folder for source
def copyFromContainerOrPartition(src, dest, partitionName, chmod = None):

    if (re.match('^partition/', src)):  # matches partition
        # create the path to the source file/directory
        source = TREDLY_PARTITIONS_MOUNT + "/" + partitionName + "/" + TREDLY_PTN_DATA_DIR_NAME + "/" + src.split('/', 1)[-1].rstrip('/')
    if (re.match('^/', src)):           # matches container
        # create the path to the source file/directory
        source = builtins.tredlyFile.fileLocation + src.rstrip('/')

    # make sure the dest exists
    if (not os.path.isdir(dest)):
        os.makedirs(dest)

    dest = dest.rstrip('/') + "/"

    # Copy the data in
    cmd = ['cp', '-R', source, dest]
    process = Popen(cmd,  stdin=PIPE, stdout=PIPE, stderr=PIPE)
    stdOut, stdErr = process.communicate()
    if (process.returncode != 0):
        # errored
        print(stdErr)
        return False
    else:
        # check if we need to change the mode
        if (chmod is not None):
            os.chmod(dest, chmod)

        # Success
        return True

# generates a uuid
def generateShortUUID(size=8, chars=string.ascii_lowercase + string.ascii_uppercase + string.digits):
    return ''.join(random.choice(chars) for _ in range(size))

def getAvailableIP4Address(networkAddr, cidr):
    # if cidr == 32 then the host is the network
    if (cidr == 32):
        return networkAddr

    # get an ipnetwork object
    network = ip_network(networkAddr + "/" + cidr)

    # get a list of hosts and select one at random
    hosts = list(network.hosts())

    foundIP = ''
    # loop until we find one thats not in use
    while (len(foundIP) == 0):
        endRand = len(list(hosts)) -1

        index = random.randint(0, endRand)

        # assign it
        ipAddress = str(hosts[index])

        # now make sure its actually unique
        if (not ip4InUse(ipAddress)):
            foundIP = ipAddress


    return foundIP

def ip4InUse(ip4):
    # now make sure its actually unique
    inUse = getIP4AddressesInUse()

    # check if its in use and return result
    for usedIp4 in inUse:
        if (ip4 == str(usedIp4)):
            return True

    return False



# get a list of ip addresses that are actually in use
def getIP4AddressesInUse():
    # get a list of ip4_addrs
    zfsPartitions = ZFSDataset(ZFS_TREDLY_DATASET)

    # get a list of ip addresses for this interface
    ip4Addrs = zfsPartitions.getPropertyRecursive(ZFS_PROP_ROOT + ':ip4_addr')

    # a list to return
    ip4s = []

    # loop over results
    for ip4Addr in ip4Addrs:
        #match bridge0|192.168.0.1/24
        regex = '^(\w+)\|([\w.]+)\/(\d+)$'

        m = re.match(regex, ip4Addr)
        ip4 = m.group(2)
        # make sure its a valid ip
        if (isValidIp4(ip4)):
            # create an ipv4 address and return
            ip4s.append(IPv4Address(ip4))

    return ip4s


def getInterfaceIP4(interface):
    if (interface is None):
        return None

    f = os.popen('ifconfig ' + interface + " | awk 'sub(/inet /,\"\"){print $1}'" )
    return f.read().strip()

# formats a filename for nginx
def nginxFormatFilename(filename):
    # swap :// for dash
    filename = filename.replace('://', '-')

    # swap dots for underscores
    filename = filename.replace('.', '_')

    # swap slashes for dashes
    filename = filename.replace('/', '-')

    return filename

# formats a filename for unbound
def unboundFormatFilename(filename):
    # base unbound filename off last 3 (sub)domains
    fileParts = filename.split('.')

    # create the filename
    if (len(fileParts) >= 3):
        filename = fileParts[-3] + '.' + fileParts[-2] + '.' + fileParts[-1]
    elif(len(fileParts) == 2):
        filename = fileParts[-2] + '.' + fileParts[-1]

    return filename

# checks whether an interface exists on the host or not
def networkInterfaceExists(interface):
    # if the interface is none then its invalid
    if (interface is None):
        return False

    ifconfig = ['ifconfig', interface]

    process = Popen(ifconfig, stdin=PIPE, stdout=PIPE, stderr=PIPE)
    stdOut, stdErr = process.communicate()
    if (process.returncode != 0):
        return False
    else:
        return True

# checks whether a hostname is valid or not
def isValidHostname(hostname):
    # make sure length isnt > 255 chars
    if (len(hostname) > 255):
        return False

    # valid hostname pattern
    pattern = '^([a-zA-Z0-9]|[a-zA-Z0-9][a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])(\.([a-zA-Z0-9]|[a-zA-Z0-9][a-zA-Z0-9\-]{0,61}[a-zA-Z0-9]))*$'

    # check if it matches
    if (re.match(pattern, hostname)):
        return True

    return False

# checks whether an ip address is valid or not
def isValidIp4(ip4):
    try:
        IPv4Address(ip4)
    except:
        return False

    return True

# check if a cidr is valid or not
def isValidCidr(cidr):
    # make sure its an int
    try:
        cidrInt = int(cidr)
    except:
        return False

    if (cidrInt < 0) or (cidrInt > 32):
        return False

    return True

# convert an ip4 address to ip6
def ip4ToIP6(ip4):
    try:
        ip4Obj = IPv4Address(ip4)
    except ValueError:
        print("Invalid ip address " + ip4)

    # convert ip4 to rfc 3056 IPv6 6to4 address
    # http://tools.ietf.org/html/rfc3056#section-2
    return str(IPv6Address(int(IPv6Address("2002::")) | (int(ip4Obj) << 80)))

# validates an ip4_addr from command line
def validateIp4Addr(ip4Addr):
    regex = '^(\w+)\|([\w.]+)\/(\d+)$'
    m = re.match(regex, ip4Addr)

    if (m is None):
        e_error('Could not validate ip4_addr "' + ip4Addr + '" - incorrect format')
        return False
    else:
        # assign from regex match
        interface = m.group(1)
        ip4 = m.group(2)
        cidr = m.group(3)

        # make sure the interface exists
        if (not networkInterfaceExists(interface)):
            e_error('Interface "' + interface + '" does not exist in "' + ip4Addr +'"')
            return False
        # validate the ip4
        if (not isValidIp4(ip4)):
            e_error('IP Address "' + ip4 + '" is invalid in "' + ip4Addr +'"')
            return False
        # validate the cidr
        if (not isValidCidr(cidr)):
            e_error('CIDR "' + cidr + '" is invalid in "' + ip4Addr + '"')
            return False

        # make sure its not already in use
        if (ip4InUse(ip4)):
            e_error("IP Address " + ip4 + ' is already in use.')
            return False

    return True

# takes a 2d list and formats it into a talbe in the same manner as the "column" binary
def formatTable(data, heading = None):
    output = ''
    minPadding = 2

    # calculate the width of the columns
    col_width = max(len(str(word)) for row in data for word in row) + minPadding

    # if we received a heading then bold each element
    if (heading is not None):
        output += formatBold + "".join(str(word).ljust(col_width) for word in heading) + "\n" + formatDefault

    # append the data
    i = 0
    for row in data:
        output += "".join(str(word).ljust(col_width) for word in row)

        # add a newline if this isnt the last element
        if (i < (len(data)-1)):
            output += "\n"

        i = i + 1

    return output
