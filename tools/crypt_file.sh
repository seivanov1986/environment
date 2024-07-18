#!/bin/bash

read fullname
pass=`echo $fullname | <checksumm> | awk '{ print $1 }'`
gpg --batch --yes --passphrase "$pass" --symmetric --cipher-algo AES<num> file.txt
