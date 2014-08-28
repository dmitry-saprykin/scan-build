# -*- coding: utf-8 -*-
#                     The LLVM Compiler Infrastructure
#
# This file is distributed under the University of Illinois Open Source
# License. See LICENSE.TXT for details.

import logging
import multiprocessing
import re
import os
import os.path
import shutil
import glob
from cgi import escape
from analyzer.decorators import trace, require
from analyzer.driver import filter_dict, get_clang_version


__all__ = ['generate_report']


@trace
@require(['sequential'])
def generate_report(args, out_dir):
    """ Report generation.

    Report is generated from .html files, and it's a .html file itself. """
    pool = multiprocessing.Pool(1 if args['sequential'] else None)
    result = 0
    with bug_fragment(
            pool.imap_unordered(scan_bug,
                                glob.iglob(os.path.join(out_dir,
                                                        '*.html'))),
            out_dir) as bugs:
        with crash_fragment(
                pool.imap_unordered(scan_crash,
                                    glob.iglob(os.path.join(out_dir,
                                                            'failures',
                                                            '*.info.txt'))),
                out_dir) as crashes:
            result = bugs.count + crashes.count
            if result > 0:
                assembly_report(args, out_dir, bugs, crashes)
                copy_resource_files(out_dir)
    pool.close()
    pool.join()
    return result


@trace
def scan_bug(result):
    """ Parse out the bug information from HTML output. """
    def classname(bug):
        def smash(key):
            return bug.get(key, '').lower().replace(' ', '_').replace("'", '')
        return 'bt_' + smash('bug_category') + '_' + smash('bug_type')

    def safe_value(container, key, encode):
        if key in container:
            value = encode(container[key])
            container.update({key: value})

    patterns = [
        re.compile(r'<!-- BUGTYPE (?P<bug_type>.*) -->$'),
        re.compile(r'<!-- BUGFILE (?P<bug_file>.*) -->$'),
        re.compile(r'<!-- BUGPATHLENGTH (?P<bug_path_length>.*) -->$'),
        re.compile(r'<!-- BUGLINE (?P<bug_line>.*) -->$'),
        re.compile(r'<!-- BUGCATEGORY (?P<bug_category>.*) -->$'),
        re.compile(r'<!-- BUGDESC (?P<bug_description>.*) -->$'),
        re.compile(r'<!-- FUNCTIONNAME (?P<bug_function>.*) -->$')]
    endsign = re.compile(r'<!-- BUGMETAEND -->')

    bug_info = dict()
    with open(result) as handler:
        for line in handler.readlines():
            # do not read the file further
            if endsign.match(line):
                break
            # search for the right lines
            for regex in patterns:
                match = regex.match(line.strip())
                if match:
                    bug_info.update(match.groupdict())

    # fix some default values
    bug_info['bug_category'] = bug_info.get('bug_category', 'Other')
    bug_info['bug_path_length'] = int(bug_info.get('bug_path_length', 1))
    bug_info['bug_line'] = int(bug_info.get('bug_line', 0))
    bug_info['report_file'] = result
    bug_info['bug_type_class'] = classname(bug_info)
    safe_value(bug_info, 'bug_category', escape)
    safe_value(bug_info, 'bug_type', escape)
    safe_value(bug_info, 'bug_type_class', lambda x: escape(x, True))

    return bug_info


@trace
def scan_crash(filename):
    """ Parse out the crash information from the report file. """
    match = re.match(r'(.*)\.info\.txt', filename)
    name = match.group(1) if match else None
    with open(filename) as handler:
        lines = handler.readlines()
        return {'source': escape(lines[0].rstrip()),
                'problem': escape(lines[1].rstrip()),
                'preproc': escape(name, True),
                'stderr': escape(name + '.stderr.txt', True)}


class ReportFragment(object):
    """ Represents a report fragment on the disk. The only usage at report
        generation, when multiple fragments are combined together. """

    def __init__(self, filename, count):
        self.filename = filename
        self.count = count

    def __enter__(self):
        return self

    @trace
    def __exit__(self, _type, _value, _traceback):
        os.remove(self.filename)

    @trace
    def write(self, output_handle):
        if self.count:
            with open(self.filename, 'r') as input_handle:
                for line in input_handle:
                    output_handle.write(line)


@trace
def crash_fragment(iterator, out_dir):
    name = os.path.join(out_dir, 'crashes.html.fragment')
    count = 0
    with open(name, 'w') as handle:
        indent = 4
        handle.write(reindent("""
        |<h2>Analyzer Failures</h2>
        |<p>The analyzer had problems processing the following files:</p>
        |<table>
        |  <thead>
        |    <tr>
        |      <td>Problem</td>
        |      <td>Source File</td>
        |      <td>Preprocessed File</td>
        |      <td>STDERR Output</td>
        |    </tr>
        |  </thead>
        |  <tbody>""", indent))
        for current in iterator:
            count += 1
            handle.write(reindent("""
        |    <tr>
        |      <td>{problem}</td>
        |      <td>{source}</td>
        |      <td><a href="{preproc}">preprocessor output</a></td>
        |      <td><a href="{stderr}">analyzer std err</a></td>
        |    </tr>""", indent).format(**current))
        handle.write(reindent("""
        |  </tbody>
        |</table>""", indent))
    return ReportFragment(name, count)


@trace
def bug_fragment(iterator, out_dir):
    def hash_bug(bug):
        return str(bug['bug_line']) + ':' +\
            str(bug['bug_path_length']) + ':' +\
            bug['bug_file'][::-1]

    def update_counters(counters, bug):
        bug_category = bug['bug_category']
        current_category = counters.get(bug_category, dict())
        bug_type = bug['bug_type']
        current_type = current_category.get(bug_type, {
            'bug_type': bug_type,
            'bug_type_class': bug['bug_type_class'],
            'bug_count': 0})
        current_type.update({'bug_count': current_type['bug_count'] + 1})
        current_category.update({bug_type: current_type})
        counters.update({bug_category: current_category})

    name = os.path.join(out_dir, 'bugs.html.fragment')
    uniques = set()
    counters = dict()
    with open(name, 'w') as handle:
        indent = 4
        handle.write(reindent("""
        |<h2>Reports</h2>
        |<table class="sortable" style="table-layout:automatic">
        |  <thead>
        |    <tr>
        |      <td>Bug Group</td>
        |      <td class="sorttable_sorted">
        |        Bug Type
        |        <span id="sorttable_sortfwdind">&nbsp;&#x25BE;</span>
        |      </td>
        |      <td>File</td>
        |      <td class="Q">Line</td>
        |      <td class="Q">Path Length</td>
        |      <td class="sorttable_nosort"></td>
        |    </tr>
        |  </thead>
        |  <tbody>""", indent))
        for current in iterator:
            bug_hash = hash_bug(current)
            if bug_hash not in uniques:
                uniques.add(bug_hash)
                update_counters(counters, current)
                handle.write(reindent("""
        |    <tr class="{bug_type_class}">
        |      <td class="DESC">{bug_category}</td>
        |      <td class="DESC">{bug_type}</td>
        |      <td>{bug_file}</td>
        |      <td class="Q">{bug_line}</td>
        |      <td class="Q">{bug_path_length}</td>
        |      <td><a href="{report_file}#EndPath">View Report</a></td>
        |    </tr>""", indent).format(**current))
        handle.write(reindent("""
        |  </tbody>
        |</table>""", indent))
    with ReportFragment(name, len(uniques)) as bugs:
        return summary_fragment(counters, out_dir, bugs)\
            if bugs.count else bugs


@trace
def summary_fragment(counters, out_dir, tail_fragment):
    name = os.path.join(out_dir, 'summary.html.fragment')
    with open(name, 'w') as handle:
        indent = 4
        handle.write(reindent("""
        |<h2>Bug Summary</h2>
        |<table>
        |  <thead>
        |    <tr>
        |      <td>Bug Type</td>
        |      <td>Quantity</td>
        |      <td class="sorttable_nosort">Display?</td>
        |    </tr>
        |  </thead>
        |  <tbody>""", indent))
        handle.write(reindent("""
        |    <tr style="font-weight:bold">
        |      <td class="SUMM_DESC">All Bugs</td>
        |      <td class="Q">{0}</td>
        |      <td>
        |        <center>
        |          <input checked type="checkbox" id="AllBugsCheck"
        |                 onClick="CopyCheckedStateToCheckButtons(this);"/>
        |        </center>
        |      </td>
        |    </tr>""", indent).format(tail_fragment.count))
        for category, types in counters.items():
            handle.write(reindent("""
        |    <tr>
        |      <th>{0}</th><th colspan=2></th>
        |    </tr>""", indent).format(category))
            for bug_type in types.values():
                handle.write(reindent("""
        |    <tr>
        |      <td class="SUMM_DESC">{bug_type}</td>
        |      <td class="Q">{bug_count}</td>
        |      <td>
        |        <center>
        |          <input checked type="checkbox"
        |                 onClick="ToggleDisplay(this,'{bug_type_class}');"/>
        |        </center>
        |      </td>
        |    </tr>""", indent).format(**bug_type))
        handle.write(reindent("""
        |  </tbody>
        |</table>""", indent))
        tail_fragment.write(handle)
    return ReportFragment(name, tail_fragment.count)


@trace
@require(['clang'])
def assembly_report(opts, out_dir, *fragments):
    import getpass
    import socket
    import sys
    import datetime

    if 'html_title' not in opts or opts['html_title'] is None:
        opts['html_title'] = os.getcwd() + ' - analyzer results'

    output = os.path.join(out_dir, 'index.html')
    with open(output, 'w') as handle:
        handle.write(reindent("""
        |<!DOCTYPE html>
        |<html>
        |  <head>
        |    <title>{html_title}</title>
        |    <link type="text/css" rel="stylesheet" href="scanview.css"/>
        |    <script type='text/javascript' src="sorttable.js"></script>
        |    <script type='text/javascript' src='selectable.js'></script>
        |  </head>
        |  <body>
        |    <h1>{html_title}</h1>
        |    <table>
        |      <tr><th>User:</th><td>{user_name}@{host_name}</td></tr>
        |      <tr><th>Working Directory:</th><td>{current_dir}</td></tr>
        |      <tr><th>Command Line:</th><td>{cmd_args}</td></tr>
        |      <tr><th>Clang Version:</th><td>{clang_version}</td></tr>
        |      <tr><th>Date:</th><td>{date}</td></tr>
        |    </table>""", 0).format(
            html_title=opts['html_title'],
            user_name=getpass.getuser(),
            host_name=socket.gethostname(),
            current_dir=os.getcwd(),
            cmd_args=' '.join(sys.argv),
            clang_version=get_clang_version(opts['clang']),
            date=datetime.datetime.today().strftime('%c')))
        for fragment in fragments:
            fragment.write(handle)
        handle.write(reindent("""
        |  </body>
        |</html>""", 0))


@trace
def copy_resource_files(out_dir):
    """ Copy the javascript and css files to the report directory. """
    this_dir, _ = os.path.split(__file__)
    resources_dir = os.path.join(this_dir, 'resources')
    shutil.copy(os.path.join(resources_dir, 'scanview.css'), out_dir)
    shutil.copy(os.path.join(resources_dir, 'sorttable.js'), out_dir)
    shutil.copy(os.path.join(resources_dir, 'selectable.js'), out_dir)


def reindent(text, indent):
    result = ''
    for line in text.splitlines():
        if len(line.strip()):
            result += ' ' * indent + line.split('|')[1] + os.linesep
    return result