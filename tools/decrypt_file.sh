#!/bin/bash

read fullname
pass=`echo $fullname | sha256sum | awk '{ print $1 }'`
gpg --batch --yes --passphrase "$pass" --cipher-algo AES256 --decrypt file.txt.encrypted > file.txt.decrypted
