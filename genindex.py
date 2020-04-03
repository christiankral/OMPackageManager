#!/usr/bin/env python3

import json
import common

def main():
  repos = json.load(open("repos.json"))
  rawdata = json.load(open("rawdata.json"))



  indexdata = {}

  with open("index.json","w") as io:
    json.dump(indexdata, io, sort_keys=True, indent=2)

if __name__ == '__main__':
  main()
