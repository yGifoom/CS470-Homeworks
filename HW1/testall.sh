#!/bin/bash

for tnum in ./given_tests/*
do
    echo "--"
    cat ${tnum}/desc.txt
    printf "\n"
    python3 main.py ${tnum}/input.json ${tnum}/user_output.json
    python3 compare.py ${tnum}/user_output.json --reference ${tnum}/output.json
done
