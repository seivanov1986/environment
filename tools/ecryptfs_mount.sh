#!/bin/bash

ENCRYPT_CIPHER= #aes, blowfish, des3_ede, twofish, cast6, cast5
ENCRYPT_KEY_BYTES= #32, 24, 16
ENCRYPT_PASSTHROUGH=no #it allows non-encrypted files to be used inside the mount
ENCRYPT_ENABLE_FILENAME_CRYPTO=yes

mount \
    -t ecryptfs ./encrypt_folder/ /decrypt_folder/ \
    -o key=passphrase,ecryptfs_cipher={$ENCRYPT_CIPHER},ecryptfs_key_bytes={$ENCRYPT_KEY_BYTES},ecryptfs_passthrough={$ENCRYPT_PASSTHROUGH},ecryptfs_enable_filename_crypto={$ENCRYPT_ENABLE_FILENAME_CRYPTO}