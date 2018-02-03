# -*- coding: utf-8 -*-


import os
from setuptools import setup
from setuptools.command.install import install as _install

import law
from law.util import which


this_dir = os.path.dirname(os.path.abspath(__file__))


with open(os.path.join(this_dir, "README.rst"), "r") as f:
    long_description = f.read()

keywords = ["luigi", "workflow", "pipeline", "remote", "submission", "grid"]

classifiers = [
    "Programming Language :: Python",
    "Programming Language :: Python :: 2",
    "Programming Language :: Python :: 3",
    "Development Status :: 4 - Beta",
    "Operating System :: OS Independent",
    "License :: OSI Approved :: MIT License",
    "Intended Audience :: Developers",
    "Intended Audience :: Science/Research",
    "Intended Audience :: Information Technology",
    "Topic :: System :: Monitoring",
]

install_requires = []
with open(os.path.join(this_dir, "requirements.txt"), "r") as f:
    install_requires.extend(line.strip() for line in f.readlines() if line.strip())


# workaround to change the installed law script to _not_ use pkg_resources
class install(_install):

    def run(self):
        _install.run(self)  # old-style

        with open(os.path.join(this_dir, "bib", "law")) as f:
            lines = f.readlines()
        with open(which("law"), "w") as f:
            f.write("".join(lines))


setup(
    name=law.__name__,
    version=law.__version__,
    author=law.__author__,
    author_email=law.__email__,
    description=law.__doc__.strip(),
    license=law.__license__,
    url=law.__contact__,
    keywords=" ".join(keywords),
    classifiers=classifiers,
    long_description=long_description,
    install_requires=install_requires,
    zip_safe=False,
    packages=[
        "law",
        "law.task",
        "law.target",
        "law.sandbox",
        "law.workflow",
        "law.job",
        "law.scripts",
        "law.contrib",
        "law.contrib.tasks",
        "law.contrib.git",
        "law.contrib.glite",
        "law.contrib.htcondor",
        "law.contrib.wlcg",
        "law.contrib.cms",
        "law.examples",
    ],
    package_data={
        "": ["LICENSE", "requirements.txt", "README.md"],
        "law": ["completion.sh"],
        "law.job": ["job.sh"],
        "law.scripts": ["law"],
        "law.contrib.git": ["bundle_repository.sh", "repository_checksum.sh"],
        "law.contrib.glite": ["wrapper.sh"],
        "law.contrib.cms": ["bundle_cmssw.sh", "cmsdashb_hooks.sh", "bin/*"],
    },
    cmdclass={"install": install},
    entry_points={"console_scripts": ["law = law.scripts.cli:main"]},
)
