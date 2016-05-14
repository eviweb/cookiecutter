#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
cookiecutter.hooks
------------------

Functions for discovering and executing various cookiecutter hooks.
"""

import io
import logging
import os
import subprocess
import sys
import tempfile
import json
import re

from jinja2 import Template

from cookiecutter import utils
from .exceptions import FailedHookException


_HOOKS = [
    'pre_gen_project',
    'post_gen_project',
    # TODO: other hooks should be listed here
]
EXIT_SUCCESS = 0


def find_hooks():
    """
    Must be called with the project template as the current working directory.
    Returns a dict of all hook scripts provided.
    Dict's key will be the hook/script's name, without extension, while
    values will be the absolute path to the script.
    Missing scripts will not be included in the returned dict.
    """
    hooks_dir = 'hooks'
    r = {}
    logging.debug('hooks_dir is {0}'.format(hooks_dir))
    if not os.path.isdir(hooks_dir):
        logging.debug('No hooks/ dir in template_dir')
        return r
    for f in os.listdir(hooks_dir):
        basename = os.path.splitext(os.path.basename(f))[0]
        if basename in _HOOKS:
            r[basename] = os.path.abspath(os.path.join(hooks_dir, f))
    return r


def run_script_with_context(script_path, cwd, context):
    """
    Executes a script either after rendering with it Jinja or in place without
    template rendering.

    :param script_path: Absolute path to the script to run.
    :param cwd: The directory to run the script from.
    :param context: Cookiecutter project template context.
    """
    if '_run_hook_in_place' in context and context['_run_hook_in_place']:
        script = script_path
    else:
        script = __create_renderable_hook(script_path, context)

    try:
        result = __do_run_script(script, cwd, json.dumps(context).encode())
        json_search = re.findall('(\{.*\})', result[0].decode())
        return json.loads(json_search[-1]) if json_search else context
    except ValueError:
        return context


def run_hook(hook_name, project_dir, context):
    """
    Try to find and execute a hook from the specified project directory.

    :param hook_name: The hook to execute.
    :param project_dir: The directory to execute the script from.
    :param context: Cookiecutter project context.
    """
    script = find_hooks().get(hook_name)
    if script is None:
        logging.debug('No hooks found')
        return context
    return run_script_with_context(script, project_dir, context)


def __create_renderable_hook(script_path, context):
    """
    Create a renderable hook by copying the real hook and applying the template

    :param script_path: Absolute path to the base hook.
    :param context: Cookiecutter project template context.
    """
    _, extension = os.path.splitext(script_path)
    contents = io.open(script_path, 'r', encoding='utf-8').read()
    with tempfile.NamedTemporaryFile(
        delete=False,
        mode='wb',
        suffix=extension
    ) as temp:
        output = Template(contents).render(**context)
        temp.write(output.encode('utf-8'))
    return temp.name


def __get_script_command(script_path):
    """
    Get the executable command of a given script

    :param script_path: Absolute path to the script to run.
    """
    if script_path.endswith('.py'):
        script_command = [sys.executable, script_path]
    else:
        script_command = [script_path]

    utils.make_executable(script_path)

    return script_command


def __do_run_script(script_path, cwd, serialized_context):
    """
    Executes a script wrinting the given serialized context to its standard
    input stream.

    :param script_path: Absolute path to the script to run.
    :param cwd: The directory to run the script from.
    :param serialized_context: Serialized Cookiecutter project template
                               context.
    """
    run_thru_shell = sys.platform.startswith('win')

    proc = subprocess.Popen(
        __get_script_command(script_path),
        shell=run_thru_shell,
        cwd=cwd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    result = proc.communicate(serialized_context)

    exit_status = proc.wait()
    if exit_status != EXIT_SUCCESS:
        raise FailedHookException(
            "Hook script failed (exit status: %d)" % exit_status)

    return result
