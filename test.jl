import GitHub
import Glob
import JSON
import LibGit2
import OMJulia

println("Start")

@enum SupportLevel fullSupport support experimental obsolete unknown noSupport

supportLevel = Dict{String,SupportLevel}("fullSupport" => fullSupport, "support" => support, "experimental" => experimental, "obsolete" => obsolete, "unknown" => unknown)

function getSupportLevel(tagName::AbstractString, levels)::SupportLevel
  local vn
  try
    vn = VersionNumber(tagName)
  catch
    return noSupport
  end
  for level in levels
    matched = false
    if level[1] == "*"
      matched = true
    elseif startswith(level[1], ">=") && vn >= VersionNumber(level[1][3:end])
      matched = true
    elseif level[1] == tagName
      matched = true
    end
    if matched
      return supportLevel[level[2]]
    end
  end
  return noSupport
end

function lessTag(x, y)
  if x["support"] == y["support"]
    return VersionNumber(x["tag"]) > VersionNumber(y["tag"])
  end
  return x["support"] < y["support"]
end

function run()
  println("Start run")
  omc = OMJulia.OMCSession()
  data = JSON.parsefile("test.json")
  serverdata = JSON.parsefile("server.json")

  myauth = GitHub.authenticate(ENV["GITHUB_AUTH"])
  #repos, page_data = GitHub.repos("modelica-3rdParty", auth=myauth)
  #for r in repos
  #  println(r)
  #end

  if !isdir("cache")
    mkdir("cache")
  end

  for key in keys(data)
    entry = data[key]
    if haskey(entry, "github")
      r = GitHub.repo(entry["github"]; auth=myauth)

      if haskey(serverdata, key) && r.updated_at == serverdata[key]["updated_at"]
        continue
      end
      if !haskey(serverdata, key)
        serverdata[key] = Dict()
      end
      if !haskey(serverdata[key], "tags")
        serverdata[key]["tags"] = Dict()
      end
      serverdata["updated_at"] = r.updated_at

      branches, page_data = GitHub.branches(r; auth=myauth)
      tags, page_data = GitHub.tags(r; auth=myauth)
      println(branches)
      tagsDict = serverdata[key]["tags"]

      repopath = joinpath("cache", key)

      for tag in tags
        tagName = match(r"/git/refs/tags/(?<name>.*)", tag.url.path)[:name]
        sha = tag.object["sha"]
        if !haskey(tagsDict, tagName)
          serverdata[key]["tags"][tagName] = Dict()
        end
        if !haskey(tagsDict, "sha") || (tagsDict[tagName]["sha"] != sha)
          ghurl = "https://github.com/" * entry["github"] * ".git"
          if isdir(repopath)
            gitrepo = LibGit2.GitRepo(repopath)
            LibGit2.fetch(gitrepo)
            if !all(h.url == ghurl for h in LibGit2.fetchheads(gitrepo))
              println("Removing repository " * ghurl)
              rm(repopath, recursive=true)
            end
          end
          if !isdir(repopath)
            LibGit2.clone(ghurl, repopath)
          end
          gitrepo = LibGit2.GitRepo(repopath)
          LibGit2.checkout!(gitrepo, sha)

          provided = Dict()
          for libname in entry["names"]
            hits = cat(
              readdir(Glob.GlobMatch(joinpath(repopath,libname*"*","package.mo"))),
              readdir(Glob.GlobMatch(joinpath(repopath,libname*"*.mo"))),
              readdir(Glob.GlobMatch(joinpath(repopath,libname*"*",libname * "*.mo"))),
              readdir(Glob.GlobMatch(joinpath(repopath,"package.mo")))
              ; dims=1
            )
            if size(hits,1) != 1
              continue
            end
            OMJulia.sendExpression(omc, "clear()")
            if !OMJulia.sendExpression(omc, "loadFile(\"" * hits[1] * "\")")
              println("Failed to load file " * OMJulia.sendExpression(omc, "getErrorString()"))
              continue
            end
            classNamesAfterLoad::Array{Symbol,1} = OMJulia.sendExpression(omc, "getClassNames()")
            if !(Symbol(libname) in classNamesAfterLoad)
              print("Did not load the library? ")
              println(classNamesAfterLoad)
              continue
            end
            version = OMJulia.sendExpression(omc, "getVersion("*libname*")")
            uses = Dict(OMJulia.sendExpression(omc, "getUses("*libname*")"))
            # Get conversions
            provided[libname] = Dict("version" => version, "uses" => uses)
          end
          if isempty(provided)
            println("Broken for " * tagName)
            tagsDict[tagName]["broken"]=true
            continue
          end
        end
        level = getSupportLevel(tagName, entry["support"])
        tagsDict[tagName]["support"] = level
        tagsDict[tagName]["sha"] = sha
        tagsDict[tagName]["libs"] = provided
      end
      # sort!(tagsSorted; lt=lessTag)
      println(tagsDict)
    end
  end

  println(GitHub.rate_limit(auth=myauth))
end

run()
