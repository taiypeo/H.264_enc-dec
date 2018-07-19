#!/bin/bash

# General dependencies
sudo apt-get install -y python3-dev pkg-config

# Library components
sudo apt-get install -y \
    libavformat-dev libavcodec-dev libavdevice-dev \
    libavutil-dev libswscale-dev libavresample-dev libavfilter-dev
