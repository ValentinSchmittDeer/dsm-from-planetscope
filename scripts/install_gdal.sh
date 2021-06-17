#!/bin/bash

# small setup script to install GDAL

set -x

PYTHONVERSION=$(python --version | cut -d " " -f 2 | cut -d "." -f 1)
OSVERSION=$(lsb_release -rs | cut -d "." -f 1)

if [[ "$OSVERSION" < "20" ]]; then
    sudo sh -c 'yes | add-apt-repository ppa:ubuntugis/ppa'
    sudo sh -c 'yes | sudo apt-get update'
fi
sudo sh -c 'yes | apt-get install gdal-bin'

if [[ "$PYTHONVERSION" == "2" ]]; then
    # assuming we are in Vagrantbox or docker setup here
    # installing gdal from debian packages (not via pip) which requires no
    # compliation
    # when used in Docker build this needs to run as root user!!!
    apt update
    yes | add-apt-repository -y ppa:ubuntugis/ppa
    yes | apt install gdal-bin python-gdal python3-gdal
else
    export CPLUS_INCLUDE_PATH=/usr/include/gdal
    export C_INCLUDE_PATH=/usr/include/gdal
    # following the useful hints on https://gist.github.com/cspanring/5680334 here,
    # "Installing GDAL in a Python virtual environment",
    # in any case this needs be done after numpy installation to have also gdal_array initialized correctly
    # pip install gdal==$(gdal-config --version) --global-option=build_ext --global-option="-I/usr/include/gdal"
fi


