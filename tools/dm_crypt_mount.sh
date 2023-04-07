#!/bin/bash

function F_check_exit
{
	result=${?}

	if [ "${#}" != "1" ]; then
		false
		F_check_exit "${FUNCNAME} error"
		exit
	fi

	if [ "${result}" -ne "0" ]; then
		echo "ERROR : ${1}"
		exit
	fi
}

function F_check_umount_exit
{
	result=${?}

	if [ "${#}" != "1" ]; then
		false
		F_check_exit "${FUNCNAME} error"
		exit
	fi

	if [ "${result}" -ne "0" ]; then
		echo "ERROR : ${1}"

		cryptsetup remove ${BASENAME}
			F_check_exit "cryptsetup"

		losetup -d ${FREELOOP}
			F_check_exit "losetup"

		exit
	fi
}

function F_encrypt_passphrase
{
    PASS=`echo ${PASSPHRASE} | md5sum | awk '{print $1}'`
	PASSPHRASE=${PASS}`echo ${PASSPHRASE} | sha1sum | awk '{print $1}'`
}

[ ! "${#}" != "2" ]
	F_check_exit "Usage : mount-crypt <command> <file>"

[ ! "$UID" -ne "0" ]
	F_check_exit "You are not superuser"

COMMAND=${1}
FILE=${2}
LOG=/tmp/log
PASSPHRASE=""
ENCRYPT_CIPHER=aes
HASH_ALGORITM=sha

[ -f "${FILE}" ] || [ -b "${FILE}" ]
	F_check_exit "File ${FILE} not exists"

BASENAME=`basename ${FILE}`

if [ "$COMMAND" == "mount" ]; then

	read -s -p "Input passphrase: " PASSPHRASE && echo -e

	PASSPHRASE=F_encrypt_passphrase ${PASSPHRASE}
	FREELOOP=`losetup -f`

	losetup ${FREELOOP} ${FILE} > ${LOG} 2>&1
		F_check_exit "losetup"

	echo ${PASSPHRASE} | cryptsetup -c ${ENCRYPT_CIPHER} -h ${HASH_ALGORITM} create ${BASENAME} ${FREELOOP} > ${LOG} 2>&1
		F_check_umount_exit "cryptsetup"

	echo "${FREELOOP}" > /tmp/crypt_${BASENAME}

	if [ ! -d "/media/${BASENAME}" ]; then
		mkdir -p "/media/${BASENAME}" > ${LOG} 2>&1
			F_check_umount_exit "mkdir mount_point"
	fi

	mount /dev/mapper/${BASENAME} "/media/${BASENAME}" > ${LOG} 2>&1
		F_check_umount_exit "mount"

elif [ "$COMMAND" == "umount" ]; then

	FREELOOP=`cat /tmp/crypt_${BASENAME}`

	umount /media/${BASENAME}
		F_check_exit "umount"

	cryptsetup remove ${BASENAME}
		F_check_exit "cryptsetup"

	losetup -d ${FREELOOP}
		F_check_exit "losetup"

elif [ "$COMMAND" == "create" ]; then

	read -s -p "Input passphrase: " PASSPHRASE && echo -e

	PASSPHRASE=F_encrypt_passphrase ${PASSPHRASE}
	FREELOOP=`losetup -f`

	losetup ${FREELOOP} ${FILE} > ${LOG} 2>&1
		F_check_exit "losetup"

	echo ${PASSPHRASE} | cryptsetup -c ${ENCRYPT_CIPHER} -h ${HASH_ALGORITM} create ${BASENAME} ${FREELOOP} > ${LOG} 2>&1
		F_check_umount_exit "cryptsetup"

	mkfs.ext3 /dev/mapper/${BASENAME}
		F_check_exit "mkfs.ext3"

	cryptsetup remove ${BASENAME}
		F_check_exit "cryptsetup"

	losetup -d ${FREELOOP}
		F_check_exit "losetup"

fi