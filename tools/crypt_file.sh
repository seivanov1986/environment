#!/bin/bash

read fullname
pass=`echo $fullname | sha256sum | awk '{ print $1 }'`
gpg --batch --yes --passphrase "$pass" --symmetric --cipher-algo AES256 file.txt
