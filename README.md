github-pulls
=========================

Introduction / Description
----------------------

github-pulls examines a project's GitHub repo and attempts to identify pull
requests associated with fixing defects.  The SHA-1's for each of the 
commits that were identified as addressing a defect are output in the
following forms: CSV, JSON, txt


Command Line Usage
----------------------

USAGE:

    github-pulls [-h] repo_owner repo_name

"repo_owner" (ex: GripQA") and "repo_name" (ex: "client-tools") are used
to form the base URL for accessing the repo's GitHub information. Both
arguments are required.

An optional configuration file, in the current working directory, named
'github-pulls.cfg' provides authentication information for the GitHub access.
If not specified, the program attempts to access GitHub without authentication.
This may cause issues both in terms of access permissions and GitHub's rate
limitation policy.


Running the program produces the following output files:
    <repo_name>_pulls.csv
    <repo_name>_pulls.json
    <repo_name>_pulls.txt


Repo Contents
----------------------

* **github-pulls** - main executable script
* github_pulls/ - library containing modules for import
* github_pulls/github_pulls.py - module containing most of the code
* github_pulls/\__init\__.py
* install.bsh - temporary install script, until I get around to setting up PyPI
* .gitignore
* LICENSE


Installation
----------------------

github-pulls currently supports
[Python 3.4](https://www.python.org/downloads/).
All testing and development was performed on Linux, your mileage on other
platforms may vary. Further, the temporary installation script will only work
in an environment that supports Bash scripting. Sorry about that. I'll do
a pip version ASAP. In the meantime, the installation steps for a Linux
environment are:

    git clone git@github.com:deansx/github-pulls.git
    cd github-pulls
    ./install.bsh

NOTE: You may need elevated priveleges to perform the install.

This script should put the command file into a directory that is in your
shell's PATH, and the library module(s) in a directory that is in your Python
installation's sys.path. You may need to modify it for your specific situation,
and you might need to run with elevated privileges.


Support
----------------------

If you have any questions, problems, or suggestions, please submit an
[issue](../../issues)

License & Copyright
----------------------

Copyright 2015 Grip QA

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
