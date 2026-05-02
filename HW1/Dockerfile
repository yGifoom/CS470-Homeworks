FROM ubuntu:22.04

# This toolchain has to setup a lot of stuff.
# python3, pip, go, rust, scala, jvm, npm, node

# Python3, pip3, jvm, gcc, g++
RUN apt update && apt install python3 python3-pip python-is-python3 wget openjdk-17-jdk-headless gnupg2 git gcc g++ make --no-install-recommends -y
