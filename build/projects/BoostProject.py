#!/bin/env python

################################################################################
#
# @file        BoostProject.py
#
# $Id: bczar.py 3656 2011-11-29 16:43:50Z hillj $
#
# @author      James H. Hill
#
################################################################################

import os
import sys

from ..Project import Project
from ..scm import Git
from os import path
import logging

#
# __create__
#
# Factory function for creating the project.
#
def __create__ ():
    return BoostProject ()

#
# @class BoostProject
#
# Implementation of the Project class for Xerces-C.
#
class BoostProject (Project):
    __location__ = 'boost'

    #
    # Default constructor
    #
    def __init__ (self):
        Project.__init__ (self, 'Boost')

    #
    # Download the Boost source files. The source files are taken from
    # trunk in the SVN repo.
    #
    def download (self, ctx):
        if ctx.use_https:
            url = 'https://github.com/boostorg/boost.git'
        else:
            url = 'git@github.com:boostorg/boost.git'
        tag = 'boost-1.61.0'
        abspath = path.abspath (path.join (ctx.prefix, self.__location__))
        Git.checkout (url, abspath, tag=tag)

    #
    # Set the project's environment variables.
    #
    def set_env_variables (self, prefix):
        abspath = path.abspath (path.join (prefix, self._location_))

        # Update the environment variables.
        os.environ['BOOST_ROOT'] = abspath

        if sys.platform == 'win32':
            os.environ['BOOST_VERSION'] = 'boost-1_56'

        from ..Utilities import append_libpath_variable
        from ..Utilities import append_path_variable

        append_libpath_variable (path.join (abspath, 'lib'))

    #
    # Validate environment for the project
    #
    def validate_environment (self):
        if 'BOOST_ROOT' not in os.environ:
            logging.getLogger ().error ('BOOST_ROOT environment variable is not defined')
            return False

        if sys.platform == 'win32' and 'BOOST_VERSION' not in os.environ:
            logging.getLogger ().error ('BOOST_VERSION environment variable is not defined')
            return False

        return True

    #
    # Update the script with details to configure the environment and
    # support the project.
    #
    # @param[in]            script          ScriptFile object
    #
    def update_script (self, prefix, script):
        abspath = path.abspath (path.join (prefix, self.__location__))

        if path.exists (abspath):
            script_path = script.get_this_variable ()
            location = os.path.join (script_path, self.__location__)

            script.begin_section ('Boost')
            script.write_env_variable ('BOOST_ROOT', location)

            # Locate the Boost version in the version source file. We are
            # going to use it to set the BOOST_VERSION environment variable.
            version_filename = path.join (abspath, 'libs', 'config', 'include', 'boost', 'version.hpp')
            version_file = open (version_filename, 'r')

            for line in version_file:
                if '#define' in line and 'BOOST_LIB_VERSION' in line:
                    BOOST_VERSION = line.replace ('"', '').split ()[2]
                    break

            version_file.close ()

            script.write_env_variable ('BOOST_VERSION', BOOST_VERSION)
            script.append_libpath_variable (path.join (location, 'lib'))

    #
    # Build the project
    #
    def build (self, ctx):
        import subprocess

        BOOST_ROOT = os.environ['BOOST_ROOT']
        project_config = path.join (BOOST_ROOT, 'project-config.jam')
        prefix_arg = '--prefix=' + BOOST_ROOT

        if sys.platform != 'win32':
            self.fix_iostreams (BOOST_ROOT)

        if not path.exists (project_config):
            # First, we need to boostrap the Boost environment.
            if sys.platform == 'win32':
              bootstrap = path.join (BOOST_ROOT, 'bootstrap.bat')
            else:
              bootstrap = path.join (BOOST_ROOT, 'bootstrap.sh')

            cmd = [bootstrap, prefix_arg]
            subprocess.check_call (cmd, cwd = BOOST_ROOT)

        # Generate the Boost headers. This line is need for Boost 1.56 or greater.
        # It may even be needed for an earlier version. To play it safe, we are going
        # to check if b2 exists. If it does, we are going to run it before calling
        # bjam to build Boost.
        if sys.platform == 'win32':
            b2 = path.join (BOOST_ROOT, 'b2.exe')
        else:
            b2 = path.join (BOOST_ROOT, 'b2')

        if path.exists (b2):
            cmd = [b2, 'headers']
            subprocess.check_call (cmd, cwd = BOOST_ROOT)

        # Now, we can actually build Boost using the local version of bjam
        bjam = path.join (BOOST_ROOT, 'bjam')

        if sys.platform == 'win32':
            toolsets = { 'vc71' : 'msvc-7.1',
                         'vc8'  : 'msvc-8.0',
                         'vc9'  : 'msvc-9.0',
                         'vc10' : 'msvc-10.0',
                         'vc11' : 'msvc-11.0',
                         'vc12' : 'msvc-12.0'}

            cmd = [bjam,
                   prefix_arg,
                   '--build-type=complete',
                   '--layout=versioned',
                   '--without-python',
                   '--without-math',
                   '--without-signals',
                   '--toolset=' + toolsets[ctx.build_type],
                   '--abbreviate-paths',
                   '-j' + ctx.threads,
                   'install']

        else:
          cmd = [bjam, prefix_arg, '--without-python', '-j' + ctx.threads, 'install', '-sNO_COMPRESSION=1']

        subprocess.check_call (cmd, cwd = BOOST_ROOT)

        # Run b2 headers to ensure all headers get copied to the correct location
        b2 = path.join (BOOST_ROOT, 'b2')
        cmd = [b2,
               prefix_arg,
               'headers']

        subprocess.check_call (cmd, cwd=BOOST_ROOT)

    #
    # Fix iostreams jamfile for linux builds
    #
    def fix_iostreams (self, boost_root):
        jamfile = os.path.join (boost_root, 'libs', 'iostreams', 'build', 'Jamfile.v2')
        bad_lines = ['      [ ac.check-library /zlib//zlib : <library>/zlib//zlib\n',
                     '        <source>zlib.cpp <source>gzip.cpp ]\n']

        with open (jamfile, 'r') as source:
            lines = source.readlines ()

        with open (jamfile, 'w') as source:
            for line in lines:
                if line in bad_lines:
                    continue
                source.write (line)
