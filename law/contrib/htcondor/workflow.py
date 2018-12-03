# -*- coding: utf-8 -*-

"""
HTCondor workflow implementation. See https://research.cs.wisc.edu/htcondor.
"""


__all__ = ["HTCondorWorkflow"]


import os
import logging
from abc import abstractmethod
from collections import OrderedDict

import luigi

from law import LocalDirectoryTarget, NO_STR, get_param
from law.workflow.remote import BaseRemoteWorkflow, BaseRemoteWorkflowProxy
from law.job.base import JobArguments
from law.contrib.htcondor.job import HTCondorJobManager, HTCondorJobFileFactory
from law.target.file import get_path
from law.parser import global_cmdline_args, add_cmdline_arg, remove_cmdline_arg
from law.util import law_src_path, merge_dicts


logger = logging.getLogger(__name__)


class HTCondorWorkflowProxy(BaseRemoteWorkflowProxy):

    workflow_type = "htcondor"

    def create_job_manager(self, **kwargs):
        return self.task.htcondor_create_job_manager(**kwargs)

    def create_job_file_factory(self, **kwargs):
        return self.task.htcondor_create_job_file_factory(**kwargs)

    def create_job_file(self, job_num, branches):
        task = self.task
        config = self.job_file_factory.Config()

        # the file postfix is pythonic range made from branches, e.g. [0, 1, 2, 4] -> "_0To5"
        postfix = "_{}To{}".format(branches[0], branches[-1] + 1)
        config.postfix = postfix
        pf = lambda s: "postfix:{}".format(s)

        # get the actual wrapper file that will be executed by the remote job
        wrapper_file = get_path(task.htcondor_wrapper_file())
        config.executable = os.path.basename(wrapper_file)

        # collect task parameters
        task_params = task.as_branch(branches[0]).cli_args(exclude={"branch"})
        task_params += global_cmdline_args()
        # add and remove some arguments
        task_params = remove_cmdline_arg(task_params, "--workers", 2)
        if task.htcondor_use_local_scheduler():
            task_params = add_cmdline_arg(task_params, "--local-scheduler")
        for arg in task.htcondor_cmdline_args() or []:
            if isinstance(arg, tuple):
                task_params = add_cmdline_arg(task_params, *arg)
            else:
                task_params = add_cmdline_arg(task_params, arg)

        # job script arguments
        job_args = JobArguments(
            task_cls=task.__class__,
            task_params=task_params,
            branches=branches,
            auto_retry=False,
            dashboard_data=self.dashboard.remote_hook_data(
                job_num, self.submission_data.attempts.get(job_num, 0)),
        )
        config.arguments = job_args.join()

        # prepare render variables
        config.render_variables = {}

        # input files
        config.input_files = [wrapper_file, law_src_path("job", "job.sh")]
        config.render_variables["job_file"] = pf("job.sh")

        # add the bootstrap file
        bootstrap_file = task.htcondor_bootstrap_file()
        if bootstrap_file:
            config.input_files.append(bootstrap_file)
            config.render_variables["bootstrap_file"] = pf(os.path.basename(bootstrap_file))

        # add the stageout file
        stageout_file = task.htcondor_stageout_file()
        if stageout_file:
            config.input_files.append(stageout_file)
            config.render_variables["stageout_file"] = pf(os.path.basename(stageout_file))

        # does the dashboard have a hook file?
        dashboard_file = self.dashboard.remote_hook_file()
        if dashboard_file:
            config.input_files.append(dashboard_file)
            config.render_variables["dashboard_file"] = pf(os.path.basename(dashboard_file))

        # output files
        config.output_files = []

        # custom content
        config.custom_content = []

        # logging
        # we do not use condor's logging mechanism since it requires that the submission directory
        # is present when it retrieves logs, and therefore we rely on the job.sh script
        config.log = None
        config.stdout = None
        config.stderr = None
        if task.transfer_logs:
            log_file = "stdall.txt"
            config.output_files.append(log_file)
            config.render_variables["log_file"] = pf(log_file)

        # we can use condor's file stageout only when the output directory is local
        # otherwise, one should use the stageout_file and stageout manually
        output_dir = task.htcondor_output_directory()
        if not isinstance(output_dir, LocalDirectoryTarget):
            del config.output_files[:]
        else:
            config.absolute_paths = True
            config.custom_content.append(("initialdir", output_dir.path))

        # task hook
        config = task.htcondor_job_config(config, job_num, branches)

        # determine basenames of input files and add that list to the render data
        input_basenames = [pf(os.path.basename(path)) for path in config.input_files[1:]]
        config.render_variables["input_files"] = " ".join(input_basenames)

        return self.job_file_factory(**config.__dict__)

    def destination_info(self):
        info = []
        if self.task.htcondor_pool != NO_STR:
            info.append(", pool: {}".format(self.task.htcondor_pool))
        if self.task.htcondor_scheduler != NO_STR:
            info.append(", scheduler: {}".format(self.task.htcondor_scheduler))
        return ", ".join(info)

    def submit_jobs(self, job_files):
        task = self.task
        pool = get_param(task.htcondor_pool)
        scheduler = get_param(task.htcondor_scheduler)

        # progress callback to inform the scheduler
        def progress_callback(i, result):
            i += 1
            if i in (1, len(job_files)) or i % 25 == 0:
                task.publish_message("submitted {}/{} job(s)".format(i, len(job_files)))

        return self.job_manager.submit_batch(job_files, pool=pool, scheduler=scheduler, retries=3,
            threads=task.threads, callback=progress_callback)


class HTCondorWorkflow(BaseRemoteWorkflow):

    workflow_proxy_cls = HTCondorWorkflowProxy

    htcondor_workflow_run_decorators = None
    htcondor_job_manager_defaults = None
    htcondor_job_file_factory_defaults = None

    htcondor_pool = luigi.Parameter(default=NO_STR, significant=False, description="target "
        "htcondor pool")
    htcondor_scheduler = luigi.Parameter(default=NO_STR, significant=False, description="target "
        "htcondor scheduler")

    exclude_params_branch = {"htcondor_pool", "htcondor_scheduler"}

    exclude_db = True

    @abstractmethod
    def htcondor_output_directory(self):
        return None

    def htcondor_workflow_requires(self):
        return OrderedDict()

    def htcondor_bootstrap_file(self):
        return None

    def htcondor_wrapper_file(self):
        return law_src_path("job", "bash_wrapper.sh")

    def htcondor_stageout_file(self):
        return None

    def htcondor_output_postfix(self):
        self.get_branch_map()
        return "_{}To{}".format(self.start_branch, self.end_branch)

    def htcondor_create_job_manager(self, **kwargs):
        kwargs = merge_dicts(self.htcondor_job_manager_defaults, kwargs)
        return HTCondorJobManager(**kwargs)

    def htcondor_create_job_file_factory(self, **kwargs):
        kwargs = merge_dicts(self.htcondor_job_file_factory_defaults, kwargs)
        return HTCondorJobFileFactory(**kwargs)

    def htcondor_job_config(self, config, job_num, branches):
        return config

    def htcondor_use_local_scheduler(self):
        return False

    def htcondor_cmdline_args(self):
        return []
