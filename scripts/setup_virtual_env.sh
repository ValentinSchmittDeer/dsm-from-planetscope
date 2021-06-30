#!/bin/bash

# small setup script to be used in Make context which is setting a up a python virtual env

# set -x

exists()
{
  command -v "$1" >/dev/null 2>&1
}


if exists pyenv; then
    pyenv install 3.5.2 --skip-existing
    pyenv virtualenv 3.5.2 dsm  # this will skip automatically if exists already
    pyenv local dsm  # activate env
else
    echo "It is strongly recommended to install pyenv for managing virtual environments."
    echo "See https://github.com/pyenv/pyenv#installation or https://realpython.com/intro-to-pyenv/#install"
    echo "Using `virtualenv` now to setup an environment based on system python..."
    python3 -m pip install --user virtualenv
    mkdir .venv && cd .venv  # here .venv is just a destination folder
    python3 -m venv dsm  # here venv is an executable of virtualenv
    source dsm/bin/activate
fi
