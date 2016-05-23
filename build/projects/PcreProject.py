#!/bin/env python

################################################################################
#
# @file        PcreProject.py
#
# $Id: PcreProject.py 3691 2012-11-06 20:43:52Z dfeiock $
#
# @author      James H. Hill
#
################################################################################

from ..Project import Project
from ..scm import Subversion

import os
import sys

from os import path
import logging

#
# __create__
#
# Factory function for creating the project.
#
def __create__ ():
    return PcreProject ()
    
#
# @class PcreProject
#
# Implementation of the Project object for the PCRE project.
#
class PcreProject (Project):
    __location__ = 'pcre'
    
    #
    # Default constructor.
    #
    def __init__ (self):
        Project.__init__ (self, 'pcre')

    #
    # Get the project's dependencies. The return value of this
    # function is a list of 1st level project dependencies.
    #
    def get_depends (self):
        return ['MPC']

    #
    # Downlaod the project's source files. The download can be from an online
    # archive, or a source code repository.
    #
    def download (self, ctx):
        if ctx.use_trunk:
            url = 'svn://vcs.exim.org/pcre/code/trunk'
        else:
            url = 'svn://vcs.exim.org/pcre/code/tags/pcre-8.38'
            
        abspath = path.abspath (path.join (ctx.prefix, self.__location__))
        Subversion.checkout (url, abspath)

    #
    # Set the project's environment variables.
    #
    def set_env_variables (self, prefix):
        abspath = path.abspath (path.join (prefix, self.__location__))
        os.environ['PCRE_ROOT'] = abspath

        from ..Utilities import append_libpath_variable
        from ..Utilities import append_path_variable

        append_libpath_variable (path.join (abspath, 'lib'))

    #
    # Validate environment for the project
    #
    def validate_environment (self):
        if 'PCRE_ROOT' not in os.environ:
            logging.getLogger ().error ('PCRE_ROOT environment variable is not defined')
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

            script.begin_section ('PCRE')
            script.write_env_variable ('PCRE_ROOT', location)
            script.append_libpath_variable (path.join (location, 'lib'))

    #
    # Build the project
    #
    def build (self, ctx):
        import subprocess
        from os.path import join, splitext
        from string import Template
       
        PCRE_ROOT = os.environ['PCRE_ROOT']

        if sys.platform == 'win32':
            import shutil
            logging.getLogger ().info ("configuring pcre for Windows...")
            
            # 0. Define the config.h file.
            config = """
#ifndef _PCRE_CONFIG_H_
#define _PCRE_CONFIG_H_

#define HAVE_DIRENT_H 1
#define HAVE_SYS_STAT_H 1
#define HAVE_SYS_TYPES_H 1
#define HAVE_UNISTD_H 1
#define HAVE_WINDOWS_H 1

#define HAVE_TYPE_TRAITS_H 1
#define HAVE_BITS_TYPE_TRAITS_H 1

#define HAVE_BCOPY 1
#define HAVE_MEMMOVE 1
#define HAVE_STRERROR 1
#define HAVE_STRTOLL 1
#define HAVE_STRTOQ 1
#define HAVE__STRTOI64 1

//#define SUPPORT_JIT 0
#define SUPPORT_PCREGREP_JIT 1
#define SUPPORT_UCP 1
#define BSR_ANYCRLF 1
#define NO_RECURSE 1

#define HAVE_LONG_LONG 1
#define HAVE_UNSIGNED_LONG_LONG 1

#define NEWLINE			10
#define POSIX_MALLOC_THRESHOLD	10
#define LINK_SIZE		2
#define MATCH_LIMIT		10000000
#define MATCH_LIMIT_RECURSION	10000000
#define PCREGREP_BUFSIZE        50000

#define MAX_NAME_SIZE	32
#define MAX_NAME_COUNT	10000

#endif  // !defined _PCRE_CONFIG_H_
"""
            config_h_filename = join (PCRE_ROOT, 'config.h')
            config_h_file = open (config_h_filename, 'w')
            config_h_file.write (config)
            config_h_file.close ()
 
            # 1. Copy pcre.h.in to pcre.h
            pcre_h_in = join (PCRE_ROOT, 'pcre.h.in')
            pcre_h = join (PCRE_ROOT, 'pcre.h')
            shutil.copyfile (pcre_h_in, pcre_h)
            
            # 2. Copy pcre_chartables.c.dist to pcre_chartables.c.
            pcre_chartables_c_dist = join (PCRE_ROOT, 'pcre_chartables.c.dist')
            pcre_chartables_c = join (PCRE_ROOT, 'pcre_chartables.c')
            shutil.copyfile (pcre_chartables_c_dist, pcre_chartables_c)
            
            # 3. Generate a workspace file for building PCRE.
            source_files = []
            excludes = ['pcre_jit_test.c',
                        'pcre_jit_compile.c',
                        'pcre_printint.c',
                        'pcre_ucp_searchfuncs.c']

            filenames = os.listdir (path.join (ctx.prefix, self.__location__))
            for filename in filenames:
                if filename.startswith ('pcre_') and filename.endswith ('.c') and not filename in excludes:
                    source_files.append (filename)
            
            project = """// -*- MPC -*-
            
project (pcre) {
  sharedname = libpcre
  
  includes  += $(PCRE_ROOT)
  
  dllout = ./lib
  libout = ./lib
  
  macros += HAVE_CONFIG_H
  
  specific (prop:windows) {
    link_options += /DEF:$(PCRE_ROOT)/libpcre.def
  }
  
  Source_Files {
"""
  
            for source_file in source_files:
                project += '    ' + source_file + '\n'
               
            project += """ 
  }
}
"""
            
            project_filename = join (PCRE_ROOT, 'pcre.mpc')
            project_file = open (project_filename, 'w')
            project_file.write (project)
            project_file.close ()

            # Write the workspace file for the project.
            workspace = """// -*- MWC -*-

workspace (pcre) {
  pcre.mpc
}
"""
            workspace_filename = join (PCRE_ROOT, 'pcre.mwc')
            workspace_file = open (workspace_filename, 'w')
            workspace_file.write (workspace)
            workspace_file.close ()

            # 4. Build the project.
            from ..MpcWorkspace import MpcContext, MpcWorkspace
            mpc_ctx = MpcContext (workspace_filename, ctx.build_type, 'Release', ctx.threads, None, True)
            mwc =  MpcWorkspace (mpc_ctx)

            mwc.generate ()
            mwc.build ()

            # 5. Install the project.
            pcre_include = join (PCRE_ROOT, 'include')
            if path.exists (pcre_include):
                shutil.rmtree (pcre_include)

            def copytree_includes (root, files):
                logging.getLogger ().info ('copying files in %s' % root)

                exts = ['.h']

                ignore = [name for name in files
                            if not splitext (name)[1] in exts]

                return ignore

            shutil.copytree (PCRE_ROOT,
                             pcre_include,
                             False,
                             copytree_includes)

            # 6. Rename the import library.
            libpcre_lib = join (PCRE_ROOT, 'lib', 'libpcre.lib')
            pcre_lib = join (PCRE_ROOT, 'lib', 'pcre.lib')
            shutil.move (libpcre_lib, pcre_lib)

        else:
            # First, we need to fix any SDO linkage problems.
            #self.fix_SDO_linkage (PCRE_ROOT)

            # We can then proceed with running automake to generate
            # the ./configure script.
            cmd = ['./autogen.sh']
            subprocess.check_call (cmd, cwd = PCRE_ROOT)

            # Execute the ./configure script so we can build PCRE
            cmd = ['./configure', '--prefix=' + PCRE_ROOT]
            subprocess.check_call (cmd, cwd = PCRE_ROOT)

            # Finally, we can build PCRE
            cmd = ['make', '-j', ctx.threads, 'install']
            subprocess.check_call (cmd, cwd = PCRE_ROOT)

    #
    # Helper method that fixes the SDO linkage error that resulted
    # from improving how ld handles dependencies at compile time.
    # As pcre-8.30, this problem has not been fixed. The simple fix
    # is to add to the end of Makefile.am: 
    #
    #   pcretest_LDADD += libpcre.la
    #   pcregrep_LDADD += libpcre.la
    #
    def fix_SDO_linkage (self, PCRE_ROOT):
      import subprocess
      automake_config = path.join (PCRE_ROOT, 'Makefile.am')

      # Update the configuration for pcretest
      cmd = ['sed', 
             's/pcretest_LDADD = libpcreposix.la $(LIBREADLINE)/pcretest_LDADD = libpcre.la libpcreposix.la $(LIBREADLINE)/',
             '-i',
             automake_config]
      subprocess.check_call (cmd, cwd = PCRE_ROOT)

      # Update the configuration for pcregrep
      cmd = ['sed', 
             's/pcregrep_LDADD = libpcreposix.la $(LIBZ) $(LIBBZ2)/pcregrep_LDADD = libpcre.la libpcreposix.la $(LIBZ) $(LIBBZ2)/',
             '-i',
             automake_config]
      subprocess.check_call (cmd, cwd = PCRE_ROOT)
