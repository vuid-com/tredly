# Performs actions requested by the user
import builtins

from objects.tredly.tredlyhost import *

from includes.util import *
from includes.defines import *
from includes.output import *

# config the host
class ActionList:
    def __init__(self, subject, target, identifier, actionArgs):
        # check the subject of this action
        if (subject == "resources"):
            # make sure target was set
            if (target is None):
                e_error("Too few arguments received.")
                exit(1)
            elif (target == "available"):
                # identifier == partition name
                self.listAvailableResources(identifier)
            else:
                e_error("No command " + target + " found.")
                exit(1)

        else:
            e_error("No command " + subject + " found.")
            exit(1)

    # list out the available resources
    def listAvailableResources(self, partitionName = None):
        e_header("Available Resources for Host")

        tredlyHost = TredlyHost()

        # get the cpu and memory details
        cpu = tredlyHost.getCpuDetails()
        memory = tredlyHost.getMemoryDetails()
        disk = tredlyHost.getDiskDetails(partitionName)

        data = []
        data.append([cpu['availableAverage'][1], memory['free'], disk['available']])

        table = formatTable(data, ['CPU', 'MEM', 'HDD'])
        print('--------------------')
        print(table)
        print('--------------------')
