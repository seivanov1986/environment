#!/bin/bash

read -p "Введите строку: " input
echo -n "$input" | sha256sum
