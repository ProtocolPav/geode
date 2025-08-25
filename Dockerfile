FROM ubuntu:24.04

RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install apt-utils -yqq && rm -rf /var/cache/apt/*

RUN DEBIAN_FRONTEND=noninteractive apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install apt-utils -yqq && DEBIAN_FRONTEND=noninteractive apt-get install python3 pip sudo curl unzip screen net-tools gawk openssl findutils pigz libicu-dev libcurl4 libc6 libcrypt1 libcurl4-openssl-dev ca-certificates binfmt-support -yqq && rm -rf /var/cache/apt/*

COPY requirements.txt amethyst/requirements.txt
RUN pip install -r amethyst/requirements.txt --break-system-packages

# IPV4 Ports
EXPOSE 19132/tcp
EXPOSE 19132/udp

# IPV6 Ports
EXPOSE 19133/tcp
EXPOSE 19133/udp

# API Port
EXPOSE 8000

ENV PYTHONPATH "${PYTHONPATH}:/amethyst/"
WORKDIR amethyst
