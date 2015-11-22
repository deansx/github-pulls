"""Examines a project's GitHub repo and attempts to identify pull
requests associated with fixing defects.  The SHA-1's for each of the 
commits that were identified as addressing a defect are output in the
following forms: CSV, JSON, txt

The primary methods are:
    analyze_pulls() - Main entry point, gets the data from GitHub, analyzes
                        it and generates the output files
    get_commits_by_pull_num() - Given a pull request number, returns the list
                        of the SHA-1's for the commits that make up the pull
                        request

analyze_pulls() produces the following output files:
    <repo_name>_pulls.csv
    <repo_name>_pulls.json
    <repo_name>_pulls.txt
    

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

"""

__author__ = "Dean Stevens"
__copyright__ = "Copyright 2015, Grip QA"
__license__ = "Apache License, Version 2.0"
__status__ = "Prototype"
__version__ = "0.0.1"


import sys
import os
import requests
import argparse
import configparser
import re
import json
import csv

from enum import Enum, unique

VERBOSE = True

REPO_BASE = "https://api.github.com/repos/"
PARAMS = [("state", "all"),("per_page", "100")]
ERR_LABEL = "ERROR: "
NOTE_LABEL = "NOTE: "
ERR_INDENT = ' '*len(ERR_LABEL)
NOTE_INDENT = ' '*len(NOTE_LABEL)
EXITING_STR = ''.join([ERR_INDENT, "Exiting...\n"])
# Set of labels that designate a pull request as representing a bug.
DEFECTS = {"bug", "defect", "kind/bug"}
#DEFECTS = {"bug", "defect", "kind/bug", "enhancement"}


@unique
class AuthType(Enum):
    oauth = 1
    pwd   = 2


def is_verbose():
    """Encapsulate the module global for clean access from scripts that
    import this one.
    Returns:
        the value of the VERBOSE variable
    """
    return VERBOSE


def get_params():
    """Encapsulate the module global for clean access from scripts that
    import this one.
    Returns:
        The list of pre-defined parameters
    """
    return PARAMS


def is_defect(pull_req, params, auth):
    """Checks the given pull request data against our criteria for
    identifying defects
    Args:
        pull_req - dict representing a single pull request
        params - list of parameter tuples
        auth - authorization information
    Returns:
        True if our analysis indicates that the issue/pull request is
        associated with addressing a defect
    """
    # Check the corresponding issue
    issue = get_page(pull_req["issue_url"], params, auth)
    labels = issue.json().get("labels", [])
    label_names = []
    for l in labels:
        label_names.append(l["name"])
    isect = DEFECTS.intersection(set(label_names))
    if isect:
        return True
    else:
        return False

def wait_it_out(msg, total_wait):
    """If our access to the repo's REST api is being rate limited, we might
    need to pause for a while to wait for our next allocation of requests.
    This function periodically let's the user know that we're still waiting
    while it waits until we can download issues again.
    Args:
        msg - str with the message to display while we're waiting
        total_wait - duration of the wait in seconds. We'll periodically
                        issue a note to the console during the wait so that
                        the user knows that we haven't died, yet...
    """
    total_wait += 15
    wait_incr = 240
    fstrlst = ["{0}{1}\n      ", "{2}", " minutes remaining..."]
    while total_wait >= 0:
        if total_wait > 60:
            mins = total_wait // 60
        else:
            mins = total_wait / 60
            fstrlst[1] = "{1:0.2f}"
        fstr = ''.join(fstrlst)+'\n'
        sys.stdout.write(fstr.format(gh_shared.NOTE_LABEL, msg, mins))
        sleep(wait_incr if total_wait > wait_incr else total_wait)
        total_wait -= wait_incr

    sys.stdout.write( ''.join([ gh_shared.NOTE_LABEL
                     ,"Wait completed, continuing execution...\n"
                     ]))


def get_page(url, params, auth):
    """Get a page of issues from the GitHub REST api
    Args:
        url - str containing the url to request
        params - list of tuples containing the parameters to accompany the
                    request
        auth - either a tuple of two strings that will be user/pwd for
                    authentication, or None
    Returns:
        The list of pull requests, if successful.
        Waits if we are rate limited
        Raises an exception if the status code has some other unsuccessful
        value
    """
    response = requests.get(url, params=params, auth=auth)
    if response.headers["x-ratelimit-remaining"] == "0":
        sys.stdout.write("Rate Limit Hit, waiting for reset...\n")
        reset = int(response.headers["x-ratelimit-reset"])
        reset_at = datetime.datetime.utcfromtimestamp(reset)
        wait_time = (reset_at - datetime.datetime.utcnow()).seconds
        sys.stdout.write("Resets at: {}\n".format(reset_at))
        sys.stdout.write("Currently: {}\n".format(datetime.datetime.utcnow()))
        sys.stdout.write("Waiting:   {} minutes\n".format(wait_time // 60))
        wait_it_out("Rate Limit Hit", wait_time)
        return get_page(url, params, auth)
    elif response.status_code == 200:
        return response
    else:
        raise Exception(response.status_code)


def download_pulls(url, params, auth):
    """Get all of the pull requests in the repo

    Args:
        url - str specifying the URL of the GitHub repo
        params - list of parameter tuples
        auth - authorization information
    Returns:
        list containing all pull request records
    """
    pull_reqs = []
    total_recs = 0
    while url is not None:
        response = get_page(url, params, auth)
        pull_list = response.json()
        pull_reqs.extend(pull_list)
        num_pulls = len(pull_list)
        total_recs += num_pulls
        fstr = "Processing {0} issues/pull requests, for {1} total\n"
        sys.stdout.write(fstr.format(num_pulls, total_recs))
        if "link" in response.headers:
            pages = dict(
                [(reln[6:-1], ref[ref.index('<')+1:-1]) for ref, reln in
                 [refs.split(';') for refs in
                  response.headers['link'].split(',')]])
            if "last" in pages and "next" in pages:
                url = pages["next"]
            else:
                url = None
        else:
            url = None
    return pull_reqs


def get_pull_requests(owner, repo, params, auth):
    """Builds up the URL for the first GET and then retrieves all of
    the repo's pull requests.

    Args:
        owner - str specifying the owner of the repo
        repo - str giving the name of the repo
        params - list of parameter tuples
        auth - authorization information
    Returns:
        list of pull request dictionary objects
    """
    url = "".join([REPO_BASE
                   ,owner
                   ,"/"
                   ,repo
                   ,"/pulls"
                   ])
    return download_pulls(url, params, auth)


def get_commits_by_url(commits_url, params, auth):
    """Extracts the commits that make up the pull represented by the given
    url for a pull.

    Args:
        commits_url - str giving the GitHub URL for the commits that make up
                    a pull request
        params - list of parameter tuples
        auth - authorization information
    Returns:
        list of commit SHA-1s that make up the given pull request
    """
    commit_shas = []
    commits = get_page(commits_url, params, auth).json()
    for c in commits:
        commit_shas.append(c["sha"])
        #print("#{0}- Cmmt: {1}".format(pull_url.split("/")[-2], c["sha"]))

    return commit_shas


def get_commits_by_pull_num(pull_num, owner, repo, params, auth):
    """Extracts the commits that make up the specified pull identified
    by its number.

    Args:
        pull_num - int specifiying the GitHub number of a specific pull
                    request
        owner - str specifying the owner of the repo
        repo - str giving the name of the repo
        params - list of parameter tuples
        auth - authorization information
    Returns:
        list of commit SHA-1s that make up the given pull request
    """
    url = "".join([REPO_BASE
                   ,owner
                   ,"/"
                   ,repo
                   ,"/pulls/"
                   ,str(pull_num)
                   ,"/commits"
                   ])
    return get_commits_by_url(url, params, auth)


def get_commits_by_pull(pull, params, auth):
    """Extracts the commits that make up the pull represented by the given
    GitHub pull dictionary.

    Args:
        pull - dict containing information about a single pull from the
                GitHub RESTful interface
        params - list of parameter tuples
        auth - authorization information
    Returns:
        list of commit SHA-1s that make up the given pull request
    """
    return get_commits_by_url(pull["commits_url"], params, auth)
    


def analyze_pulls(owner, repo, params, auth=None):
    """Main processing method for this module.
    Given the repo and auth information, extracts the pull requests and
    analyzes them to determine which ones were assocated with addressing
    defects. For those that were, captures the pull request's SHA-1
    The results are saved to a file.

    Args:
        owner - str specifying the owner of the repo
        repo - str giving the name of the repo
        params - list of parameter tuples
        auth - authorization information
    Returns:
        the list of SHA-1 values, produces the output files
    """
    pulls = get_pull_requests(owner, repo, params, auth)
    shas = []
    # We'll use this dictionary to generate JSON and CSV
    pull_commits = {}
    ns1 = ("{0}Checking for defects associated with "
             "pull requests.\n").format(NOTE_LABEL)
    ns2 = "{0}This might take a bit of time...\n".format(NOTE_INDENT)
    sys.stdout.write("{0}{1}".format(ns1, ns2))
    if VERBOSE:
        progress = 0
    for p in pulls:
        if VERBOSE:
            if progress // 10 > 0:
                sys.stdout.write("*")
            progress += 1
            if progress == 71:
                sys.stdout.write("\n")
                progress = 0

        if is_defect(p, params, auth):
            # print("#{0}- Head: {1}".format(p["number"], p["head"]["sha"]))
            # print("#{0}- Base: {1}".format(p["number"], p["base"]["sha"]))
            commits = get_commits_by_pull(p, params, auth)
            #shas.append(p["head"]["sha"])
            shas.extend(commits)
            pull_commits[p["number"]] = commits
                         

    if VERBOSE:
        sys.stdout.write("\n")

    # Generate the text format file
    with open(''.join(["./", repo, "_pulls.txt"]), 'w') as f:
            for s in shas:
                f.write("{}\n".format(s))

    # Generate the CSV
    with open(''.join(["./", repo, "_pulls.csv"]), 'w', newline='') as f:
        writer = csv.writer( f
                            ,quoting=csv.QUOTE_MINIMAL
                            ,lineterminator=os.linesep
                           )
        writer.writerow(["Pull", "Commit-SHA", "Owner", "Repo"])
        for p in pull_commits:
            for s in pull_commits[p]:
                writer.writerow([p,s, owner, repo])

    # Generate the JSON
    # WARNING: We're adding data to the commit dictionary for the JSON
    #          output. After this, it will no longer be suited for row
    #          based output
    json_out = {
                 "owner":owner
                ,"repo":repo
                ,"pull_requests":pull_commits
               }
    with open(''.join(["./", repo, "_pulls.json"]), 'w') as f:
        json.dump(json_out, f)


    
    return shas


def load_config_data(config_file_path):
    """Loads the configuration data, if possible.

    Args:
        config_file_path - str containing the filesystem path to the config
                            file
    Returns:
        The Default section of the configuration dicitonary object
    """
    config = configparser.ConfigParser(interpolation=None)
    if config.read(config_file_path):
        fstr = "{0}Using configuration file: '{1}'\n"
        sys.stderr.write(fstr.format(NOTE_LABEL, config_file_path))
    else:
        fstr = "{0}Unable to open configuration file: '{1}'\n{2}"
        sys.stderr.write(fstr.format(ERR_LABEL, config_file_path, EXITING_STR))
        sys.exit(1)

    return config["DEFAULT"]



def get_auth(config_file_path):
    """Extracts the authentication info from the config file
    For now, just user & pwd, OAuth to be added soon

    Args:
        config_file_path - str containing the filesystem path to the config
                            file
    Returns:
        tuple containing the appropriate auth information
    """
    cfg = load_config_data(config_file_path)
  
    auth_t = AuthType(AuthType.pwd)
    
    # Username/Password
    if auth_t is AuthType.pwd:
        user = cfg["User"]
        pwd  = cfg["Pwd"]
        if user is not None and pwd is not None:
            return (user, pwd)
        else:
            fstr = ("{0}Username/Password must be specified in config file\n"
                    "{1}")
            sys.stderr.write(fstr.format(ERR_LABEL, EXITING_STR))
            sys.exit(1)
    else:
        fstr = "{0}Unable to handle Authorization type: {1}\n{2}"
        sys.stderr.write(fstr.format(ERR_LABEL, auth_t, EXITING_STR))
        sys.exit(1)

