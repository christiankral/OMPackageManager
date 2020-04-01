#!/usr/bin/env python3

import OMPython
import os
from github import Github
import json
import pygit2
import glob
import semantic_version

def VersionNumber(s):
  if s.startswith("v"):
    s = s[1:]
  return semantic_version.Version.coerce(s)

def removerepo(ghurl, repopath):
  print("Removing repository " + ghurl)
  os.path.rmtree(repopath)

def findMatchingLevel(s, levels):
  try:
    vn = VersionNumber(s)
  except:
    return
  for level in levels:
    matched = False
    if level[0] == "*":
      matched = True
    elif level[0].startswith(">=") and vn >= VersionNumber(level[0][2:]):
      matched = True
    elif level[0] == s:
      matched = True
    if matched:
      return level[1]
  return

def getSupportLevel(tagName, levels):
  res = findMatchingLevel(tagName, levels)
  if res is None:
    return "noSupport"
  if res not in ["fullSupport", "support", "experimental", "obsolete", "unknown", "noSupport"]:
    return "noSupport"
  return res

def main():
  gh_auth = os.environ["GITHUB_AUTH"]
  g = Github(gh_auth)

  omc = OMPython.OMCSessionZMQ()

  data = json.load(open("test.json"))
  if os.path.exists("server.json"):
    serverdata = json.load(open("server.json"))
  else:
    serverdata = {}

  if not os.path.exists("cache"):
    os.mkdir("cache")

  namesInFile = set()
  for key in data.keys():
    for name in data[key]["names"]:
      if name in namesInFile:
        raise Exception(key + " exists multiple times")
      namesInFile.add(name)

  for key in data.keys():
    entry = data[key]
    if "github" in entry:
      r = g.get_repo(entry["github"])

      if key not in serverdata:
        serverdata[key] = {}
        print("Did not have stored data for " + key)
      if "tags" not in serverdata[key]:
        serverdata[key]["tags"] = {}
      ignoreTags = set()
      if "ignore-tags" in entry:
        ignoreTags = set(entry["ignore-tags"])
      branches = list(r.get_branches())
      tags = list(r.get_tags())
      objects = []
      for b in branches:
        if b.name in (entry.get("branches") or []):
          objects.append((entry["branches"][b.name], b.commit.sha))
      for t in tags:
        if t.name not in ignoreTags:
          objects.append((t.name, t.commit.sha))

      tagsDict = serverdata[key]["tags"]
      repopath = os.path.join("cache", key)

      for (tagName, sha) in objects:
        if tagName not in tagsDict:
          tagsDict[tagName] = {}
        thisTag = tagsDict[tagName]

        if ("sha" not in thisTag) or (thisTag["sha"] != sha):
          ghurl = "https://github.com/%s.git" % entry["github"]
          if os.path.exists(repopath):
            gitrepo = pygit2.Repository(repopath)
            if len(gitrepo.remotes) != 1:
              removerepo(ghurl, repopath)
            else:
              gitrepo.remotes[0].fetch()
          if not os.path.exists(repopath):
            pygit2.clone_repository(ghurl, repopath)
          gitrepo = pygit2.Repository(repopath)
          gitrepo.checkout_tree(gitrepo.get(sha), strategy = pygit2.GIT_CHECKOUT_FORCE | pygit2.GIT_CHECKOUT_RECREATE_MISSING)

          provided = {}
          for libname in entry["names"]:
            hits = glob.glob(os.path.join(repopath,"package.mo"))
            if len(hits) == 1:
              if libname != entry["names"][0]:
                continue
            else:
              hits = (glob.glob(os.path.join(repopath,libname,"package.mo")) +
                glob.glob(os.path.join(repopath,libname+" *","package.mo")) +
                glob.glob(os.path.join(repopath,libname+".mo")) +
                glob.glob(os.path.join(repopath,libname+" *.mo")) +
                glob.glob(os.path.join(repopath,libname+"*",libname + ".mo")) +
                glob.glob(os.path.join(repopath,libname+"*",libname + " *.mo")))
            if len(hits) != 1:
              print(str(len(hits)) + " hits for " + libname + " in " + tagName)
              continue
            omc.sendExpression("clear()")
            if "standard" in entry:
              grammar = findMatchingLevel(tagName, entry["standard"])
              if grammar is None:
                grammar = "latest"
            else:
              grammar = "latest"
            omc.sendExpression("setCommandLineOptions(\"--std=%s\")" % grammar)

            if not omc.sendExpression("loadFile(\"%s\")" % hits[0]):
              print("Failed to load file %s in %s" % (hits[0], tagName)) # OMJulia.sendExpression(omc, "OpenModelica.Scripting.getErrorString()"))
              continue
            classNamesAfterLoad = omc.sendExpression("getClassNames()")
            if libname not in classNamesAfterLoad:
              print("Did not load the library? ")
              print(classNamesAfterLoad)
              continue
            version = omc.sendExpression("getVersion(%s)" % libname)
            version = str(VersionNumber(tagName) if version == "" else VersionNumber(version))
            uses = sorted([[e[0],str(VersionNumber(e[1]))] for e in omc.sendExpression("getUses(%s)" % libname)])
            # Get conversions
            provided[libname] = {"version": version, "uses": uses}
          if len(provided) == 0:
            print("Broken for " + key + " " + tagName)
            thisTag["broken"]=True
            continue
          thisTag["libs"] = provided
          thisTag["sha"] = sha
        level = getSupportLevel(tagName, entry["support"])
        thisTag["support"] = level
      serverdata[key]["tags"] = tagsDict

  with open("server.json","w") as io:
    json.dump(serverdata, io, sort_keys=True, indent=2)
if __name__ == '__main__':
  main()
