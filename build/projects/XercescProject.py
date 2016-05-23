#!/bin/env python

################################################################################
#
# @file        XercescProject.py
#
# $Id: XercescProject.py 3702 2013-01-22 14:23:21Z dfeiock $
#
# @author      James H. Hill
#
################################################################################

import os
import sys

from os import path
from ..scm import Subversion
from ..Project import Project
import logging

#
# __create__
#
# Factory function for creating the project.
#
def __create__ ():
    return XercescProject ()
    
#
# @class XercescProject
#
# Implementation of the Project class for Xerces-C.
#
class XercescProject (Project):
    #
    # Default constructor.
    #
    def __init__ (self):
        Project.__init__ (self, 'XercesC')

        self.__location__ = 'xerces-c-3.1.3'
        self.__dll_version__ = '3_1'
        self._basename_ = self.__location__
        
    #
    # Download the Xerces-C source files. The source files are taken from
    # trunk in the SVN repo.
    #
    def download (self, ctx):
        abspath = path.abspath (path.join (ctx.prefix, self.__location__))
        if not path.exists (abspath):
            from ..Utilities import autodetect_build_type
            build_type = autodetect_build_type ()

            if ctx.use_trunk or (build_type == 'vc11'):
                url = 'https://svn.apache.org/repos/asf/xerces/c/trunk'
                Subversion.checkout (url, abspath, 'anonymous', 'anonymous')

                # Trunk checkouts do not have the configure script required for
                # linux builds.  It must be generated using the helper script reconf
                if sys.platform != 'win32':
                  import subprocess
                  cmd = ['./reconf']
                  subprocess.check_call (cmd, cwd = abspath)
            else:
                # Download the SQLite source files, which are provided in a tarball
                # that can be download from the web. We are then going to unpackage
                # the tarball so we can build it later.
                if sys.platform == 'win32':
                    archive = self._basename_ + '.zip'
                else:
                    archive = self._basename_ + '.tar.gz'
              
                url = 'http://www.apache.org/dist/xerces/c/3/sources/' + archive
                localfile = os.path.join (ctx.prefix, archive)

                from ..Utilities import download_url
                download_url (url, localfile)

                # Unpackage the archive, and remove it from disk.
                from ..Utilities import unpackage_archive
                unpackage_archive (localfile, os.path.abspath (ctx.prefix))
                
                os.remove (localfile)
        else:
            logging.getLogger ().info ('{0} already exists; skipping...'.format (abspath))

    #
    # Set the project's environment variables.
    #
    def set_env_variables (self, prefix):
        abspath = os.path.abspath (os.path.join (prefix, self.__location__))
        os.environ['XERCESCROOT'] = abspath

        from ..Utilities import append_libpath_variable
        from ..Utilities import append_path_variable

        append_libpath_variable (os.path.join (abspath, 'lib'))

    #
    # Validate environment for the project
    #
    def validate_environment (self):
        if 'XERCESCROOT' not in os.environ:
            logging.getLogger ().error ('XERCESCROOT environment variable is not defined')
            return False

        return True

    #
    # Update the script with details to configure the environment and
    # support the project.
    #
    # @param[in]            script          ScriptFile object
    #
    def update_script (self, prefix, script):
        abspath = os.path.abspath (os.path.join (prefix, self.__location__))

        if path.exists (abspath):
            script_path = script.get_this_variable ()
            location = os.path.join (script_path, self.__location__)

            script.begin_section ('Xerces-C')
            script.write_env_variable ('XERCESCROOT', location)
            script.write_env_variable ('XERCESC_VERSION', self.__dll_version__)
            script.append_libpath_variable (os.path.join (location, 'lib'))

    #
    # Build the project
    #
    def build (self, ctx):
        import subprocess
        
        XERCESCROOT = os.environ['XERCESCROOT']

        # First, we need to boostrap the Xerces-C environment.
        platform = sys.platform

        if platform == 'win32':
            import shutil
            
            # Avoid name collision with variable
            import platform as platform_lib
            
            if platform_lib.architecture()[0] == "64bit":
                platform = "x64"
          
            sln = 'projects/Win32/%s/xerces-all/xerces-all.sln' % ctx.build_type.upper ()
            configs = ['Debug|%s' % platform,
                       'Release|%s' % platform,
                       'Static Debug|%s' % platform,
                       'Static Release|%s' % platform]

            # Make sure the library path exists.
            libpath = os.path.join (XERCESCROOT, 'lib')
            if not os.path.exists (libpath):
                os.mkdir (libpath)

            for config in configs:
                from ..Utilities import get_vc_executable
                cmd = [get_vc_executable (), sln, '/useenv', '/Project', 'XercesLib']
                cmd.extend (['/Build', config])

                subprocess.check_call (cmd, cwd = XERCESCROOT)

                # Copy all output files to the library path.
                tmp = config.split ('|')
                platform = tmp[1]

                if platform.lower () == 'x64':
                    platform = 'Win64'

                build = 'Build/%s/%s/%s' % (platform, ctx.build_type.upper (), tmp[0])
                outdir = os.path.join (XERCESCROOT, build)

                for file in os.listdir (outdir):
                    path = os.path.normpath (os.path.join (outdir, file))
                    if os.path.isfile (path):
                        logging.getLogger ().info ('copying {0} to {1}'.format (path, libpath))
                        shutil.copy (path, libpath)

            # Now that we are done building the project, we need to
            # populate the include directory.
            import shutil

            include = os.path.join (XERCESCROOT, 'include')
            if os.path.exists (include):
                shutil.rmtree (include)

            def copytree_callback (root, files):
                logging.getLogger ().info ('copying files in {0}'.format (root))

                excludes = ['.svn']
                exts = ['.hpp', '.c']

                ignore = [name for name in files if
                            name in excludes or
                                (os.path.isfile (os.path.join (root, name)) and not os.path.splitext (name)[1] in exts)]

                return ignore

            src = os.path.join (XERCESCROOT, 'src')
            shutil.copytree (src,
                             include,
                             False,
                             copytree_callback)

        else:
            # Let's configure Xerces-C using the new configuration script.
            cmd = ['./configure', '--prefix=' + XERCESCROOT]
            subprocess.check_call (cmd, cwd = XERCESCROOT)

            cmd = ['make', '-j', ctx.threads, 'install']
            subprocess.check_call (cmd, cwd = XERCESCROOT)

    #
    # Build the project
    #
    def clean (self, ctx):
        import subprocess
        
        XERCESCROOT = os.environ['XERCESCROOT']

        # First, we need to boostrap the Xerces-C environment.
        platform = sys.platform

        if platform == 'win32':
            import shutil

            sln = 'projects/Win32/%s/xerces-all/xerces-all.sln' % ctx.build_type.upper ()
            configs = ['Debug|Win32',
                       'Release|Win32',
                       'Static Debug|Win32',
                       'Static Release|Win32']

            # Make sure the library path exists.
            libpath = os.path.join (XERCESCROOT, 'lib')
            if not os.path.exists (libpath):
                os.mkdir (libpath)

            for config in configs:
                from ..Utilities import get_vc_executable
                cmd = [get_vc_executable (), sln, '/useenv', '/Project', 'XercesLib']
                cmd.extend (['/Clean', config])

                subprocess.check_call (cmd, cwd = XERCESCROOT)

            # Now that we are done cleaning the project, we need to
            # populate the include directory.
            import shutil

            include = os.path.join (XERCESCROOT, 'include')
            if os.path.exists (include):
                shutil.rmtree (include)

        else:
            # Let's configure Xerces-C using the new configuration script.
            cmd = ['make', 'clean']
            subprocess.check_call (cmd, cwd = XERCESCROOT)
