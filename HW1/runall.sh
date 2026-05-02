#!/bin/bash

for tnum in ./given_tests/*
do
    python3 main.py ${tnum}/input.json ${tnum}/user_output.json
done
