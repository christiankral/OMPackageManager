#!/usr/bin/env python3

import semantic_version

def VersionNumber(s):
  if s.startswith("v"):
    s = s[1:]
  try:
    return semantic_version.Version.coerce(s)
  except:
    return

def findMatchingLevel(s, levels):
  try:
    vn = VersionNumber(s)
  except:
    return
  for level in levels:
    matched = False
    if level[0] == "prerelease" and len(vn.prerelease)>0:
      return level[1]
    elif level[0] == "*":
      return level[1]
    elif level[0].startswith(">=") and vn >= VersionNumber(level[0][2:]):
      return level[1]
    elif level[0] == s:
      return level[1]
  return

def getSupportLevel(tagName, levels):
  res = findMatchingLevel(tagName, levels)
  if res is None:
    return "noSupport"
  if res not in ["fullSupport", "support", "experimental", "obsolete", "unknown", "noSupport"]:
    return "noSupport"
  return res
