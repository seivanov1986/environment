#!/bin/bash

qemu-system-x86_64 \
  -enable-kvm -cpu host \
  -m 2048 -smp 2 \
  -drive file=ubuntu.qcow,if=virtio,format=qcow2 \
  -netdev user,id=net0,hostfwd=tcp::5555-:22 \
  -device virtio-net-pci,netdev=net0 \
  -display none \
  -serial file:/srv/qemu/qemu-serial.log \
  -daemonize