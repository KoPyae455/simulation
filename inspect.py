#!/usr/bin/env python3
p = "/home/kopyae/Git/simulaca/simulaca_brain/app/modules/cognition/brain_service.py"
lines = open(p).readlines()
for i in range(174, 212):
    print(f"{i+1}: {lines[i]}", end="")
