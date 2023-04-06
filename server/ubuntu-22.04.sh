#/bin/bash

apt-get -y remove docker docker-engine docker.io containerd runc
apt-get update
apt-get -y install \
  ca-certificates \
  curl \
  gnupg \
  lsb-release
mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/debian/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
echo \
  "deb [arch="$(dpkg --print-architecture)" signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  "$(. /etc/os-release && echo "$VERSION_CODENAME")" stable" |   sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
apt-get update
apt-get -y install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

curl -L "https://github.com/docker/compose/releases/download/1.29.2/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

apt-get -y install mc vim gdisk

#gdisk /dev/sdb #n, w
#mkfs.ext4 /dev/sdb1

#gdisk /dev/sdc #n, w
#mkfs.ext4 /dev/sdc1

#blkid /dev/sdb1
#blkid /dev/sdc1

#UUID=ebd9e6c6-aafe-44a1-b70f-5ae95eb52d7d /media/sdb1/ ext4 defaults 0 0
#UUID=b892ee04-2a01-46fc-9e5f-de8c2e975e1c /media/sdc1/ ext4 defaults 0 0

# cat '{"data-root": "/media/sdb1/docker/"}' /etc/docker/daemon.json

#cat 'dockin() { docker exec -it "$1" /bin/bash; }' > ~/.bashrc
#cat 'dockps() { docker ps --format "table {{.ID}}\t{{.Image}}\t{{.Names}}\t{{.Status}}"; }' > ~/.bashrc