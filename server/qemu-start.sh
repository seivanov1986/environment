#!/bin/bash

echo "allow virbr0" > /etc/qemu/bridge.conf
chmod 0640 /etc/qemu/bridge.conf

#qemu-system-x86_64 -hda ubuntu.qcow -m 8048 -vnc :1 -device e1000,netdev=net0 -netdev user,id=net0,hostfwd=tcp::5555-:22,hostfwd=tcp::55601-:5601 -smp cores=3,threads=1,sockets=4 -nographic &
qemu-system-x86_64 -hda ubuntu.qcow -m 8048 -device e1000,netdev=net0 -net bridge,br=virbr0 -netdev user,id=net0,hostfwd=tcp::5555-:22,hostfwd=tcp::55601-:5601 -smp cores=2,threads=1,sockets=4 -nographic &
