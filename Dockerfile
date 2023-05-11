FROM ubuntu:21.10 AS build

RUN apt install libssl1.1 && rm -rf /var/cache/apt/*

FROM ubuntu:22.04

COPY --from=build /usr/lib/x86_64-linux-gnu/libssl.so.1.1 /usr/lib/x86_64-linux-gnu/libssl.so.1.1
COPY --from=build /usr/lib/x86_64-linux-gnu/libcrypto.so.1.1 /usr/lib/x86_64-linux-gnu/libcrypto.so.1.1

RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install apt-utils -yqq && rm -rf /var/cache/apt/*

RUN DEBIAN_FRONTEND=noninteractive apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install apt-utils -yqq && DEBIAN_FRONTEND=noninteractive apt-get install python3 pip sudo curl unzip screen net-tools gawk openssl findutils pigz libcurl4 libc6 libcrypt1 libcurl4-openssl-dev ca-certificates binfmt-support -yqq && rm -rf /var/cache/apt/*

RUN mkdir server
    # && curl -H 'Cache-Control: no-cache, no-store' https://minecraft.azureedge.net/bin-linux/bedrock-server-1.19.1.01.zip --output server/1.19.1.zip && unzip server/1.19.1.zip -d server/1.19.1

COPY requirements.txt /requirements.txt
RUN pip install -r /requirements.txt

RUN curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip" && unzip awscliv2.zip && sudo ./aws/install

# Set port environment variables
ENV PortIPV4=19132
ENV PortIPV6=19133

# Version environment variable (must exist on Microsoft's servers)
ENV Version=1

# IPV4 Ports
EXPOSE 19132/tcp
EXPOSE 8000
EXPOSE 19132/udp

# IPV6 Ports
EXPOSE 19133/tcp
EXPOSE 19133/udp


