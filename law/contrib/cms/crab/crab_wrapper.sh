#!/usr/bin/env bash

# Wrapper script that is to be configured as crab's scriptExe file and that
# - sets up files and objects needed for crab to consider this a standard job,
# - renders variables in other job input files, and
# - runs the actual job file with arguments that depend on the crab job number.

# disable exiting at first error and command-echoing
set +e
set +v

action() {
    #
    # detect variables
    #

    local shell_is_zsh="$( [ -z "${ZSH_VERSION}" ] && echo "false" || echo "true" )"
    local this_file="$( ${shell_is_zsh} && echo "${(%):-%x}" || echo "${BASH_SOURCE[0]}" )"
    local this_file_base="$( basename "${this_file}" )"

    export LAW_CRAB_JOB_NUMBER="$( ls -1 | grep -Po "jobReport\.json\.\K\d+" | head -n 1 )"
    echo "running ${this_file_base} for job number ${LAW_CRAB_JOB_NUMBER}"


    #
    # patch edmProvDump
    #

    MD5SUM="$( cat "${this_file}" | md5sum | awk '{print $1}' )"

    cat <<EOF > "${CMSSW_BASE}/bin/${SCRAM_ARCH}/edmProvDump"
#!/bin/sh
echo "Processing History:"
echo "  USER '' '\"${CMSSW_VERSION}\"' [1]  (${MD5SUM})"
EOF

    chmod +x "${CMSSW_BASE}/bin/${SCRAM_ARCH}/edmProvDump"


    #
    # create dummy outputs
    #

    # output file as defined in the job report below
    # (not required if disableAutomaticOutputCollection is set, but kept here as a good default)
    touch out.root

    # job report
cat <<EOF > FrameworkJobReport.xml
<FrameworkJobReport>
  <InputFile>
    <LFN></LFN>
    <PFN></PFN>
    <Catalog></Catalog>
    <InputType>primaryFiles</InputType>
    <ModuleLabel>source</ModuleLabel>
    <GUID></GUID>
    <InputSourceClass>PoolSource</InputSourceClass>
    <EventsRead>1</EventsRead>
  </InputFile>

  <File>
    <LFN></LFN>
    <PFN>out.root</PFN>
    <Catalog></Catalog>
    <ModuleLabel>USER</ModuleLabel>
    <GUID></GUID>
    <OutputModuleClass>PoolOutputModule</OutputModuleClass>
    <TotalEvents>1</TotalEvents>
    <BranchHash>806a51af4d0c43b79de23e695823bf38</BranchHash>
  </File>

  <ReadBranches>
  </ReadBranches>

  <GeneratorInfo>
  </GeneratorInfo>

  <PerformanceReport>
    <PerformanceSummary Metric="StorageStatistics">
      <Metric Name="Parameter-untracked-bool-enabled" Value="true"/>
      <Metric Name="Parameter-untracked-bool-stats" Value="true"/>
      <Metric Name="Parameter-untracked-string-cacheHint" Value="application-only"/>
      <Metric Name="Parameter-untracked-string-readHint" Value="auto-detect"/>
      <Metric Name="ROOT-tfile-read-totalMegabytes" Value="0"/>
      <Metric Name="ROOT-tfile-write-totalMegabytes" Value="0"/>
    </PerformanceSummary>
  </PerformanceReport>

</FrameworkJobReport>
EOF


    #
    # job argument definitons, depending on LAW_CRAB_JOB_NUMBER
    #

    # definition
    local crab_job_arguments_map
    declare -A crab_job_arguments_map
    crab_job_arguments_map=(
        {{crab_job_arguments_map}}
    )

    # pick
    local crab_job_arguments="${crab_job_arguments_map[${LAW_CRAB_JOB_NUMBER}]}"
    if [ -z "${crab_job_arguments}" ]; then
        >&2 echo "empty crab job arguments for LAW_CRAB_JOB_NUMBER ${LAW_CRAB_JOB_NUMBER}"
        return "1"
    fi


    #
    # variable rendering
    #

    # check variables
    local render_variables="{{render_variables}}"
    if [ -z "${render_variables}" ]; then
        >&2 echo "empty render variables"
        return "2"
    fi

    # decode
    render_variables="$( echo "${render_variables}" | base64 --decode )"

    # check files to render
    local input_files_render="{{input_files_render}}"
    if [ -z "${input_files_render}" ]; then
        >&2 echo "received empty input files for rendering for LAW_CRAB_JOB_NUMBER ${LAW_CRAB_JOB_NUMBER}"
        return "3"
    fi

    # render files
    local input_file_render
    for input_file_render in ${input_files_render}; do
        # skip if the file refers to _this_ one
        local input_file_render_base="$( basename "${input_file_render}" )"
        [ "${input_file_render_base}" = "${this_file_base}" ] && continue
        # render
        python -c "\
import re;\
repl = ${render_variables};\
repl['input_files_render'] = '';\
content = open('${input_file_render}', 'r').read();\
content = re.sub(r'\{\{(\w+)\}\}', lambda m: repl.get(m.group(1), ''), content);\
open('${input_file_render_base}', 'w').write(content);\
"
        local render_ret="$?"
        # handle rendering errors
        if [ "${render_ret}" != "0" ]; then
            >&2 echo "input file rendering failed with code ${render_ret}"
            return "4"
        fi
    done


    #
    # run the actual job file
    #

    # check the job file
    local job_file="{{job_file}}"
    if [ ! -f "${job_file}" ]; then
        >&2 echo "job file '${job_file}' does not exist"
        return "5"
    fi

    # print its contents
    echo "=== content of job file '${job_file}'"
    echo
    cat "${job_file}"
    echo
    echo "=== end of job file content"

    # run it
    bash "${job_file}" ${crab_job_arguments}
}

action "$@"
