#!/usr/local/bin/bash

# set this to true to stop after every command is issued so that output can be observed
_TREDLYINSTALLDEBUG="false"

# set some bash error handlers
#set -u              # exit when attempting to use an undeclared variable
set -o pipefail     # exit when piped commands fail

# get the path to the directory this script is in
_DIR="$( cd -P "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# load the common vars
source ${_DIR}/install.vars.sh

# load the libs
for f in ${_DIR}/../tredly-libs/bash-common/*.sh; do source ${f}; done
for f in ${_DIR}/../tredly-libs/bash-install/*.sh; do source ${f}; done

# make sure this script is running as root
cmn_assert_running_as_root

# get a list of external interfaces
IFS=$'\n' declare -a _externalInterfaces=($( get_external_interfaces ))

# Check if VIMAGE module is loaded
_vimageInstalled=$( sysctl kern.conftxt | grep '^options[[:space:]]VIMAGE$' | wc -l )

###############################
declare -a _configOptions

# path to installer config
_TREDLY_DIR_CONF="${_DIR}/../../conf"

# check if the install config file exists
if [[ ! -f "${_TREDLY_DIR_CONF}/install.conf" ]]; then
    exit_with_error "Could not find conf/install.conf"
fi

# load the config file
common_conf_parse "install"
# ensure required fields are set
common_conf_validate "enableSSHD,enableAPI,enableCommandCenter,commandCenterURL,tredlyApiGit,tredlyApiBranch,tredlyCCGit,tredlyCCBranch,downloadKernelSource"

_configOptions[0]=''
# check if some values are set, and if they arent then consult the host for the details
if [[ -z "${_CONF_COMMON[externalInterface]}" ]]; then
    _configOptions[1]="${_externalInterfaces[0]}"
else
    _configOptions[1]="${_CONF_COMMON[externalInterface]}"
fi

if [[ -z "${_CONF_COMMON[externalIP]}" ]]; then
    _configOptions[2]="$( getInterfaceIP "${_externalInterfaces[0]}" )/$( getInterfaceCIDR "${_externalInterfaces[0]}" )"
else
    _configOptions[2]="${_CONF_COMMON[externalIP]}"
fi

if [[ -z "${_CONF_COMMON[externalGateway]}" ]]; then
    _configOptions[3]="$( getDefaultGateway )"
else
    _configOptions[3]="${_CONF_COMMON[externalGateway]}"
fi

if [[ -z "${_CONF_COMMON[hostname]}" ]]; then
    _configOptions[4]="${HOSTNAME}"
else
    _configOptions[4]="${_CONF_COMMON[hostname]}"
fi

if [[ -z "${_CONF_COMMON[containerSubnet]}" ]]; then
    _configOptions[5]="10.99.0.0/16"
else
    _configOptions[5]="${_CONF_COMMON[containerSubnet]}"
fi

if [[ -z "${_CONF_COMMON[apiWhitelist]}" ]]; then
    _configOptions[6]=""
else
    _configOptions[6]="${_CONF_COMMON[apiWhitelist]}"
fi
if [[ -z "${_CONF_COMMON[commandCenterURL]}" ]]; then
    _configOptions[7]=""
else
    _configOptions[7]="${_CONF_COMMON[commandCenterURL]}"
fi

# Root user password
if [[ -z "${_CONF_COMMON[rootUserPassword]}" ]]; then
    _configOptions[8]="tredly"
else
    _configOptions[8]="${_CONF_COMMON[rootUserPassword]}"
fi

# Tredly user password
if [[ -z "${_CONF_COMMON[tredlyUserPassword]}" ]]; then
    _configOptions[9]="tredly"
else
    _configOptions[9]="${_CONF_COMMON[tredlyUserPassword]}"
fi

# Tredly API password
if [[ -z "${_CONF_COMMON[tredlyApiPassword]}" ]]; then
    _configOptions[10]="tredly"
else
    _configOptions[10]="${_CONF_COMMON[tredlyApiPassword]}"
fi

# check for a dhcp leases file for this interface
#if [[ -f "/var/db/dhclient.leases.${_configOptions[1]}" ]]; then
    # look for its current ip address within the leases file
    #_numLeases=$( grep -E "${DEFAULT_EXT_IP}" "/var/db/dhclient.leases.${_configOptions[1]}" | wc -l )

    #if [[ ${_numLeases} -gt 0 ]]; then
        # found a current lease for this ip address so throw a warning
        #echo -e "${_colourMagenta}=============================================================================="
        #echo -e "${_formatBold}WARNING!${_formatReset}${_colourMagenta} The current IP address ${DEFAULT_EXT_IP} was set using DHCP!"
        #echo "It is recommended that this address be changed to be outside of your DHCP pool"
        #echo -e "==============================================================================${_colourDefault}"
    #fi
#fi

# check if we are doing an unattended installation or not
if [[ "${_CONF_COMMON[unattendedInstall]}" != "yes" ]]; then
    # run the menu
    tredlyHostMenuConfig
fi

# extract the net and cidr from the container subnet we are using
CONTAINER_SUBNET_NET="$( lcut "${_configOptions[5]}" '/')"
CONTAINER_SUBNET_CIDR="$( rcut "${_configOptions[5]}" '/')"
# Get the default host ip address on the private container network
_hostPrivateIP=$( get_last_usable_ip4_in_network "${CONTAINER_SUBNET_NET}" "${CONTAINER_SUBNET_CIDR}" )

####
e_header "Tredly Installation"

##########
e_note "Configuring users"
_exitCode=0
# set root password
echo "${_configOptions[8]}" | /usr/sbin/pw usermod root -h 0
_exitCode=$(( ${_exitCode} & $? ))
# set root to use bash shell
/usr/sbin/pw usermod root -s /usr/local/bin/bash
_exitCode=$(( ${_exitCode} & $? ))

# set up tredly user and password with bash shell
echo "${_configOptions[8]}" | /usr/sbin/pw useradd -n tredly -s /usr/local/bin/bash -m -h 0
_exitCode=$(( ${_exitCode} & $? ))

# add tredly user to wheel group for su access
pw groupmod wheel -m tredly
_exitCode=$(( ${_exitCode} & $? ))

if [[ $? -eq 0 ]]; then
    e_success "Success"
else
    e_error "Failed"
fi

##########

# Configure /etc/rc.conf
e_note "Configuring /etc/rc.conf"
_exitCode=0
# rename the existing rc.conf if it exists
if [[ -f "/etc/rc.conf" ]]; then
    mv /etc/rc.conf /etc/rc.conf.old
fi
_exitCode=$(( ${_exitCode} & $? ))
cp ${_DIR}/os/etc/rc.conf /etc/
_exitCode=$(( ${_exitCode} & $? ))
# change the network information in rc.conf
sed -i '' "s|ifconfig_bridge0=.*|ifconfig_bridge0=\"addm ${_configOptions[1]} up\"|g" "/etc/rc.conf"
_exitCode=$(( ${_exitCode} & $? ))
if [[ $? -eq 0 ]]; then
    e_success "Success"
else
    e_error "Failed"
fi

if [[ "${_TREDLYINSTALLDEBUG}" == 'true' ]]; then
    read -p "press any key to continue" confirm
fi
##########

# if vimage is installed, enable cloned interfaces
if [[ ${_vimageInstalled} -ne 0 ]]; then
    e_note "Enabling Cloned Interfaces"
    service netif cloneup
    if [[ $? -eq 0 ]]; then
        e_success "Success"
    else
        e_error "Failed"
    fi
fi

if [[ "${_TREDLYINSTALLDEBUG}" == 'true' ]]; then
    read -p "press any key to continue" confirm
fi
##########
_exitCode=0
# Update FreeBSD and install updates
e_note "Fetching and Installing FreeBSD Updates"
# install our custom freebsd update that prevents kernel updates
if [[ -f "/usr/local/etc/pkg.conf" ]]; then
    mv /etc/freebsd-update.conf /etc/freebsd-update.conf.old
fi
cp ${_DIR}/os/etc/freebsd-update.conf /etc/
_exitCode=$(( ${_exitCode} & $? ))

freebsd-update fetch install | tee -a "${_LOGFILE}"
_exitCode=$(( ${PIPESTATUS[0]} & ${_exitCode} ))

if [[ ${_exitCode} -eq 0 ]]; then
    e_success "Success"
else
    e_error "Failed"
fi

##########

# set up pkg
e_note "Configuring PKG"
if [[ -f "/usr/local/etc/pkg.conf" ]]; then
    mv /usr/local/etc/pkg.conf /usr/local/etc/pkg.conf.old
fi
cp ${_DIR}/os/usr/local/etc/pkg.conf /usr/local/etc/
if [[ $? -eq 0 ]]; then
    e_success "Success"
else
    e_error "Failed"
fi

if [[ "${_TREDLYINSTALLDEBUG}" == 'true' ]]; then
    read -p "press any key to continue" confirm
fi
##########

# Install Packages
e_note "Installing Packages"
_exitCode=0
pkg install -y ca_root_nss | tee -a "${_LOGFILE}"
_exitCode=$(( ${PIPESTATUS[0]} & $? ))
if [[ ${_exitCode} -ne 0 ]]; then
    exit_with_error "Failed to download ca_root_nss"
fi
pkg install -y vim-lite | tee -a "${_LOGFILE}"
_exitCode=$(( ${PIPESTATUS[0]} & $? ))
if [[ ${_exitCode} -ne 0 ]]; then
    exit_with_error "Failed to download vim-lite"
fi
pkg install -y rsync | tee -a "${_LOGFILE}"
_exitCode=$(( ${PIPESTATUS[0]} & $? ))
if [[ ${_exitCode} -ne 0 ]]; then
    exit_with_error "Failed to download rsync"
fi
pkg install -y openntpd | tee -a "${_LOGFILE}"
_exitCode=$(( ${PIPESTATUS[0]} & $? ))
if [[ ${_exitCode} -ne 0 ]]; then
    exit_with_error "Failed to download openntpd"
fi
pkg install -y git | tee -a "${_LOGFILE}"
_exitCode=$(( ${PIPESTATUS[0]} & $? ))
if [[ ${_exitCode} -ne 0 ]]; then
    exit_with_error "Failed to download git"
fi
pkg install -y python35 | tee -a "${_LOGFILE}"
_exitCode=$(( ${PIPESTATUS[0]} & $? ))
if [[ ${_exitCode} -ne 0 ]]; then
    exit_with_error "Failed to download python 3.5"
fi
pkg install -y py27-fail2ban | tee -a "${_LOGFILE}"
_exitCode=$(( ${PIPESTATUS[0]} & $? ))
if [[ ${_exitCode} -ne 0 ]]; then
    exit_with_error "Failed to download fail2ban"
fi
pkg install -y nginx | tee -a "${_LOGFILE}"
_exitCode=$(( ${PIPESTATUS[0]} & $? ))
if [[ ${_exitCode} -ne 0 ]]; then
    exit_with_error "Failed to download Nginx"
fi
pkg install -y unbound | tee -a "${_LOGFILE}"
_exitCode=$(( ${PIPESTATUS[0]} & $? ))
if [[ ${_exitCode} -ne 0 ]]; then
    exit_with_error "Failed to download Unbound"
fi

if [[ ${_exitCode} -eq 0 ]]; then
    e_success "Success"
else
    e_error "Failed"
fi

if [[ "${_TREDLYINSTALLDEBUG}" == 'true' ]]; then
    read -p "press any key to continue" confirm
fi
##########

# check if user wanted to enable SSHD or not
if [[ $( str_to_lower "${_CONF_COMMON[enableSSHD]}") == 'yes' ]]; then
    # Configure SSH
    _exitCode=0
    e_note "Configuring SSHD"

    # if the user has their own sshd config then preserve it
    if [[ -f "/etc/ssh/sshd_config" ]]; then
        mv /etc/ssh/sshd_config /etc/ssh/sshd_config.old
        _exitCode=$(( ${_exitCode} & $? ))
    fi
    
    cp ${_DIR}/os/etc/ssh/sshd_config /etc/ssh/sshd_config
    _exitCode=$(( ${_exitCode} & $? ))
    
    # change the networking data for ssh
    sed -i '' "s|ListenAddress .*|ListenAddress ${_configOptions[2]}|g" "/etc/ssh/sshd_config"
    _exitCode=$(( ${_exitCode} & $? ))
    
    # enable it in rc.conf
    echo 'sshd_enable="YES"' >> /etc/rc.conf
    _exitCode=$(( ${_exitCode} & $? ))
    
    if [[ ${_exitCode} -eq 0 ]]; then
        e_success "Success"
    else
        e_error "Failed"
    fi
else
    e_note "Skipping configuration of SSHD"
fi

if [[ "${_TREDLYINSTALLDEBUG}" == 'true' ]]; then
    read -p "press any key to continue" confirm
fi
##########

# Configure Vim
e_note "Configuring VIM"
cp ${_DIR}/os/usr/local/share/vimrc /usr/local/share/vim/vimrc
if [[ $? -eq 0 ]]; then
    e_success "Success"
else
    e_error "Failed"
fi

if [[ "${_TREDLYINSTALLDEBUG}" == 'true' ]]; then
    read -p "press any key to continue" confirm
fi
##########

# Configure IPFW
e_note "Configuring IPFW"
_exitCode=0
mkdir -p /usr/local/etc
_exitCode=$(( ${_exitCode} & $? ))
cp ${_DIR}/os/usr/local/etc/ipfw.rules /usr/local/etc/ipfw.rules
_exitCode=$(( ${_exitCode} & $? ))
cp ${_DIR}/os/usr/local/etc/ipfw.layer4 /usr/local/etc/ipfw.layer4
_exitCode=$(( ${_exitCode} & $? ))
cp ${_DIR}/os/usr/local/etc/ipfw.vars /usr/local/etc/ipfw.vars
_exitCode=$(( ${_exitCode} & $? ))

# Removed ipfw start for now due to its ability to disconnect a user from their host
#service ipfw start
#_exitCode=$(( ${_exitCode} & $? ))
if [[ ${_exitCode} -eq 0 ]]; then
    e_success "Success"
else
    e_error "Failed"
fi

if [[ "${_TREDLYINSTALLDEBUG}" == 'true' ]]; then
    read -p "press any key to continue" confirm
fi

##########
# Configure Fail2ban
e_note "Configuring Fail2Ban"
cp "${_DIR}/fail2ban/ssh-ipfw.conf" "/usr/local/etc/fail2ban/jail.d/ssh-ipfw.conf"
_exitCode=$(( ${_exitCode} & $? ))
cp "${_DIR}/fail2ban/action/ipfw-ssh.conf" "/usr/local/etc/fail2ban/action.d/ipfw-ssh.conf"
_exitCode=$(( ${_exitCode} & $? ))
if [[ ${_exitCode} -eq 0 ]]; then
    e_success "Success"
else
    e_error "Failed"
fi

if [[ "${_TREDLYINSTALLDEBUG}" == 'true' ]]; then
    read -p "press any key to continue" confirm
fi
##########

# Configure OpenNTP
_exitCode=0
e_note "Configuring OpenNTP"
if [[ -f "/usr/local/etc/ntpd.conf" ]]; then
    mv /usr/local/etc/ntpd.conf /usr/local/etc/ntpd.conf.old
fi
cp ${_DIR}/os/usr/local/etc/ntpd.conf /usr/local/etc/
_exitCode=$(( ${_exitCode} & $? ))
if [[ ${_exitCode} -eq 0 ]]; then
    e_success "Success"
else
    e_error "Failed"
fi

if [[ "${_TREDLYINSTALLDEBUG}" == 'true' ]]; then
    read -p "press any key to continue" confirm
fi
##########

# Configure zfs scrubbing
#vim /etc/periodic.conf

##########

# Change kernel options
e_note "Configuring kernel options"
_exitCode=0

if [[ -f "/boot/loader.conf" ]]; then
    mv /boot/loader.conf /boot/loader.conf.old
fi
cp ${_DIR}/os/boot/loader.conf /boot/
if [[ $? -eq 0 ]]; then
    e_success "Success"
else
    e_error "Failed"
fi

e_note "Configuring Sysctl"

if [[ -f "/etc/sysctl.conf" ]]; then
    mv /etc/sysctl.conf /etc/sysctl.conf.old
fi
cp ${_DIR}/os/etc/sysctl.conf /etc/
if [[ $? -eq 0 ]]; then
    e_success "Success"
else
    e_error "Failed"
fi

if [[ "${_TREDLYINSTALLDEBUG}" == 'true' ]]; then
    read -p "press any key to continue" confirm
fi
##########

# Configure fstab for bash
if [[ $( grep /dev/fd /etc/fstab | wc -l ) -eq 0 ]]; then
    e_note "Configuring Bash"
    echo "fdesc                   /dev/fd fdescfs rw              0       0" >> /etc/fstab
    if [[ $? -eq 0 ]]; then
        e_success "Success"
    else
        e_error "Failed"
    fi
fi

if [[ "${_TREDLYINSTALLDEBUG}" == 'true' ]]; then
    read -p "press any key to continue" confirm
fi
##########

# Configure HTTP Proxy
e_note "Configuring Layer 7 (HTTP) Proxy"
_exitCode=0
mkdir -p /usr/local/etc/nginx/access
_exitCode=$(( ${_exitCode} & $? ))
mkdir -p /usr/local/etc/nginx/server_name
_exitCode=$(( ${_exitCode} & $? ))
mkdir -p /usr/local/etc/nginx/proxy_pass
_exitCode=$(( ${_exitCode} & $? ))
mkdir -p /usr/local/etc/nginx/ssl
_exitCode=$(( ${_exitCode} & $? ))
mkdir -p /usr/local/etc/nginx/upstream
_exitCode=$(( ${_exitCode} & $? ))
cp ${_DIR}/proxy/nginx.conf /usr/local/etc/nginx/
_exitCode=$(( ${_exitCode} & $? ))
cp -R ${_DIR}/proxy/proxy_pass /usr/local/etc/nginx/
_exitCode=$(( ${_exitCode} & $? ))
cp -R ${_DIR}/proxy/tredly_error_docs /usr/local/etc/nginx/
_exitCode=$(( ${_exitCode} & $? ))
if [[ ${_exitCode} -eq 0 ]]; then
    e_success "Success"
else
    e_error "Failed"
fi

if [[ "${_TREDLYINSTALLDEBUG}" == 'true' ]]; then
    read -p "press any key to continue" confirm
fi
##########

# Configure Unbound DNS
e_note "Configuring Unbound"
_exitCode=0
mkdir -p /usr/local/etc/unbound/configs
_exitCode=$(( ${_exitCode} & $? ))
cp ${_DIR}/dns/unbound.conf /usr/local/etc/unbound/
_exitCode=$(( ${_exitCode} & $? ))
if [[ ${_exitCode} -eq 0 ]]; then
    e_success "Success"
else
    e_error "Failed"
fi

if [[ "${_TREDLYINSTALLDEBUG}" == 'true' ]]; then
    read -p "press any key to continue" confirm
fi
##########
_exitCode=0
e_note "Configuring Python"
# install pip
/usr/local/bin/python3.5 -m ensurepip
_exitCode=$(( ${PIPESTATUS[0]} & $? ))
# install python libraries
/usr/local/bin/pip3 install jsonschema
_exitCode=$(( ${PIPESTATUS[0]} & $? ))
/usr/local/bin/pip3 install pyyaml
_exitCode=$(( ${PIPESTATUS[0]} & $? ))

if [[ ${_exitCode} -eq 0 ]]; then
    e_success "Success"
else
    e_error "Failed"
fi

if [[ "${_TREDLYINSTALLDEBUG}" == 'true' ]]; then
    read -p "press any key to continue" confirm
fi
##########

# install tredly common libs
e_note "Installing Tredly-Lib"
_exitCode=0

# install the libraries
${_DIR}/../tredly-libs/install.sh install clean

if [[ ${_exitCode} -eq 0 ]]; then
    e_success "Success"
else
    e_error "Failed"
fi

if [[ "${_TREDLYINSTALLDEBUG}" == 'true' ]]; then
    read -p "press any key to continue" confirm
fi
##########
e_note "Installing Tredly-Core"

# install tredly-core
${_DIR}/../tredly/install.sh install clean
if [[ $? -eq 0 ]]; then
    e_success "Success"
else
    e_error "Failed"
fi

if [[ "${_TREDLYINSTALLDEBUG}" == 'true' ]]; then
    read -p "press any key to continue" confirm
fi
##########
e_note "Installing Tredly-Host"

# install tredly-host
${_DIR}/../tredly-host/install.sh install clean
if [[ $? -eq 0 ]]; then
    e_success "Success"
else
    e_error "Failed"
fi

if [[ "${_TREDLYINSTALLDEBUG}" == 'true' ]]; then
    read -p "press any key to continue" confirm
fi
##########

# Install tredly-build
e_note "Installing Tredly-Build"

${_DIR}/../tredly-build/install.sh install clean
if [[ $? -eq 0 ]]; then
    e_success "Success"
else
    e_error "Failed"
fi

_filesLocation=''
# if we're installing from the ISO then use the ISO files
if [[ "${TREDLYISOINSTALLER}" == "true" ]]; then
    _filesLocation="/usr/freebsd-dist"
fi

if [[ "${_TREDLYINSTALLDEBUG}" == 'true' ]]; then
    read -p "press any key to continue" confirm
fi

# initialise tredly
/usr/local/sbin/tredly init

if [[ "${_TREDLYINSTALLDEBUG}" == 'true' ]]; then
    read -p "press any key to continue" confirm
fi
##########

# if the user wanted to install the api then go ahead
if [[ $( str_to_lower "${_CONF_COMMON[enableAPI]}") == 'yes' ]]; then
    # set the path for nodejs
    export PATH="${PATH}:/usr/local/bin"
    # set up tredly api
    e_note "Configuring Tredly-API"
    _exitCode=1
    cd /tmp
    # if the directory for tredly-api already exists, then delete it and start again
    if [[ -d "/tmp/tredly-api" ]]; then
        echo "Cleaning previously downloaded Tredly-API"
        rm -rf /tmp/tredly-api
    fi
    
    while [[ ${_exitCode} -ne 0 ]]; do
        /usr/local/bin/git clone -b "${_CONF_COMMON[tredlyApiBranch]}" "${_CONF_COMMON[tredlyApiGit]}"
        _exitCode=$?
    done
    
    cd /tmp/tredly-api
    
    # install the API and extract the random password so we can present this to the user at the end of install
    echo "${_configOptions[10]}" | ./install.sh
    #apiPassword="$( ./install.sh | grep "^Your API password is: " | cut -d':' -f 2 | sed -e 's/^[ \t]*//' )"
    
    if [[ ${PIPESTATUS[0]} -eq 0 ]]; then
        e_success "Success"
    else
        e_error "Failed"
    fi
else
    e_note "Skipping Tredly-API Installation"
fi

if [[ "${_TREDLYINSTALLDEBUG}" == 'true' ]]; then
    echo "${PATH}"
    read -p "press any key to continue" confirm
fi
##########

# install command center if user requested it
if [[ $( str_to_lower "${_CONF_COMMON[enableCommandCenter]}") == 'yes' ]]; then
    e_note "Configuring Tredly Command Center"
    _exitCode=1
    cd /tmp
    # if the directory for tredly-cc already exists, then delete it and start again
    if [[ -d "/tmp/tredly-cc" ]]; then
        echo "Cleaning previously downloaded Tredly Command Center"
        rm -rf /tmp/tredly-cc
    fi

    while [[ ${_exitCode} -ne 0 ]]; do
        /usr/local/bin/git clone -b "${_CONF_COMMON[tredlyCCBranch]}" "${_CONF_COMMON[tredlyCCGit]}"
        _exitCode=$?
    done

    cd /tmp/tredly-cc
    
    # install the Command Center using the url we were given
    ./install.sh "${_configOptions[7]}"
    
    if [[ $? -eq 0 ]]; then
        e_success "Success"
    else
        e_error "Failed"
    fi
else
    e_note "Skipping Tredly Command Center Installation"
fi

if [[ "${_TREDLYINSTALLDEBUG}" == 'true' ]]; then
    read -p "press any key to continue" confirm
fi
##########

# Setup crontab
e_note "Configuring Crontab"
_exitCode=0
mkdir -p /usr/local/host/
_exitCode=$(( ${_exitCode} & $? ))
cp ${_DIR}/os/usr/local/host/crontab /usr/local/host/
_exitCode=$(( ${_exitCode} & $? ))
crontab /usr/local/host/crontab
_exitCode=$(( ${_exitCode} & $? ))
if [[ ${_exitCode} -eq 0 ]]; then
    e_success "Success"
else
    e_error "Failed"
fi

if [[ ${_vimageInstalled} -ne 0 ]] || [[ "${TREDLYISOINSTALLER}" == "true" ]]; then
    e_success "Skipping kernel recompile as this kernel appears to already have VIMAGE compiled."
else
    e_note "Recompiling kernel as this kernel does not have VIMAGE built in"

    # lets compile the kernel for VIMAGE!

    # fetch the source if the user said yes or the source doesnt exist
    if [[ "$( str_to_lower "${_CONF_COMMON[downloadKernelSource]}" )" == 'yes' ]] || [[ ! -d '/usr/src/sys' ]]; then
        _thisRelease=$( sysctl -n kern.osrelease | cut -d '-' -f 1 -f 2 )
        
        # download manifest file to validate src.txz
        fetch https://download.freebsd.org/ftp/releases/amd64/${_thisRelease}/MANIFEST -o /tmp
        
        # if we have downlaoded src.txz for tredly then use that
        if [[ -f /tredly/downloads/${_thisRelease}/src.txz ]]; then
            e_note "Copying pre-downloaded src.txz"
            
            cp /tredly/downloads/${_thisRelease}/src.txz /tmp
        else
            # otherwise download the src file
            fetch https://download.freebsd.org/ftp/releases/amd64/${_thisRelease}/src.txz -o /tmp
        fi
        
        # validate src.txz against MANIFEST
        _upstreamHash=$( cat /tmp/MANIFEST | grep ^src.txz | awk -F" " '{ print $2 }' )
        _localHash=$( sha256 -q /tmp/src.txz )

        if [[ "${_upstreamHash}" != "${_localHash}" ]]; then
            # remove it as it is of no use to us
            rm -f /tmp/src.txz
            # exit and print error
            exit_with_error "Validation failed on src.txz. Please try installing again."
        else
            e_success "Validation passed for src.txz"
        fi
        
        if [[ $? -ne 0 ]]; then
            exit_with_error "Failed to download src.txz"
        fi

        # move the old source to another dir if it already exists
        if [[ -d "/usr/src/sys" ]]; then
            # clean up the old source
            mv /usr/src/sys /usr/src/sys.`date +%s`
        fi

        # unpack new source
        tar -C / -xzf /tmp/src.txz
        if [[ $? -ne 0 ]]; then
            exit_with_error "Failed to unpack src.txz"
        fi
    fi
    
    cd /usr/src
    
    # clean up any previously failed builds
    if [[ $( ls -1 /usr/obj | wc -l ) -gt 0 ]]; then
        e_note "Cleaning previously compiled Kernel"
        chflags -R noschg /usr/obj/usr >> "${_KERNELCOMPILELOG}"
        rm -rf /usr/obj/usr >> "${_KERNELCOMPILELOG}"
        make cleandir >> "${_KERNELCOMPILELOG}"
        make cleandir >> "${_KERNELCOMPILELOG}"
    fi

    # copy in the tredly kernel configuration file
    cp ${_DIR}/kernel/TREDLY /usr/src/sys/amd64/conf

    # work out how many cpus are available to this machine, and use 80% of them to speed up compile
    _availCpus=$( sysctl -n hw.ncpu )
    _useCpus=$( echo "scale=2; ${_availCpus}*0.8" | bc | cut -d'.' -f 1 )

    # if we have a value less than 1 then set it to 1
    if [[ ${_useCpus} -lt 1 ]]; then
        _useCpus=1
    fi

    e_note "Compiling kernel using 80% of available CPU resources (${_useCpus} CPUs)"
    e_note "This may take some time..."
    make -j${_useCpus} buildkernel KERNCONF=TREDLY >> "${_KERNELCOMPILELOG}"

    # only install the kernel if the build succeeded
    if [[ $? -eq 0 ]]; then
        e_note "Installing New Kernel"
        make installkernel KERNCONF=TREDLY >> "${_KERNELCOMPILELOG}"
        
        if [[ $? -ne 0 ]]; then
            exit_with_error "Failed to install kernel"
        fi
    else
        exit_with_error "Failed to build kernel"
    fi
fi

# delete the src.txz file from /tmp to save on space
if [[ -f "/tmp/src.txz" ]]; then
    rm -f /tmp/src.txz
fi

if [[ "${_TREDLYINSTALLDEBUG}" == 'true' ]]; then
    read -p "press any key to continue" confirm
fi
##########

# use tredly to set network details
/usr/local/sbin/tredly config host network "${_configOptions[1]}" "${_configOptions[2]}" "${_configOptions[3]}"
if [[ "${_TREDLYINSTALLDEBUG}" == 'true' ]]; then
    read -p "press any key to continue" confirm
fi
/usr/local/sbin/tredly config host hostname "${_configOptions[4]}"
if [[ "${_TREDLYINSTALLDEBUG}" == 'true' ]]; then
    read -p "press any key to continue" confirm
fi
/usr/local/sbin/tredly config container subnet "${_configOptions[5]}"
if [[ "${_TREDLYINSTALLDEBUG}" == 'true' ]]; then
    read -p "press any key to continue" confirm
fi
/usr/local/sbin/tredly config host DNS "8.8.8.8,8.8.4.4"
if [[ "${_TREDLYINSTALLDEBUG}" == 'true' ]]; then
    read -p "press any key to continue" confirm
fi

# if whitelist was given to us then set it up
if [[ -n "${_CONF_COMMON[apiWhitelist]}" ]]; then
    e_note "Whitelisting IP addresses for API"
    # clear the whitelist in case of old entries
    /usr/local/sbin/tredly config api whitelist clear > /dev/null
    
    declare -a _whitelistArray
    IFS=',' read -ra _whitelistArray <<< "${_CONF_COMMON[apiWhitelist]}"
    
    _exitCode=0
    for ip in ${_whitelistArray[@]}; do
        /usr/local/sbin/tredly config api whitelist "${ip}" > /dev/null
        _exitCode=$(( ${_exitCode} & $? ))
    done
    
    if [[ ${_exitCode} -eq 0 ]]; then
        e_success "Success"
    else
        e_error "Failed"
    fi
fi

# echo out confirmation message to user
e_header "Install Complete"
echo -e "${_colourMagenta}"
echo ""
echo "To change your API password, please run the command 'tredly config api password'"
echo "To whitelist addresses to access the API, please run the command 'tredly config api whitelist <ipaddr1>,<ipaddr2>'"
echo "Please note that the SSH port has changed. Please use the following command to connect to your host after reboot:"
echo "ssh -p 65222 tredly@$( lcut "${_configOptions[2]}" "/" )"
echo -e "${_formatReset}"

exit 0