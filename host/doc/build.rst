build.sh
========

*Main build script*

.. _build_abstract:

This script is the entry point of the embedded application build tools.

It is the main script to use for building the embedded applications and
documentation.

The default behaviour of the script is to detect from all direct subdirectories
with ones contain buildable content, and to build them one after another.

The build order (inter-project dependencies) is described, in each buildable
sub-directory, within the :ref:`build.dep <build_dep>` file.

Default build settings may be defined with the help of the
:ref:`build.conf <build_conf>` project configuration file.

This script always performs out-of-source builds: this means that the generated
build files - such as temporary, object, library and application files - are
created in a parallel directory tree: no file is generated within the source
tree, and the `build` output directory follows the same tree structure as the
source tree. Required build sub-directories are created when needed.

The script, as all other tools, is expected to be launch from the top-level
project directory, that is the directory that contains the `sdk`, `ecos` and
`host` sub-directories.

See the :ref:`project_specs` to obtain information about how projects are
specified, detected, validated and ordered for build.

Usage
-----

::

  build.sh [options] [projects]

  Build up embedded application projects

    -h            Print this help message
    -B            Ignore any build.conf configuration file
    -c            Clean up any build directory
    -C            Clean up all, including Python binaries & leave (no build)
    -d            Build in DEBUG mode (default: enabled), overriding project conf
    -D            Build all projects in DEBUG mode
    -F            Force exact tool versions and build modes (for production)
    -j nbproc     Spwan nbproc parallel builds at once (speed up build)
    -k            Keep going, ignore errors
    -K            Skip build stage, only create project build files (CMake)
    -l [prj:]comp Limit doc generation to this component (may be repeated)
    -n            Do no build, only generate Make/Ninja files
    -N            Include function names into the code (for debugging purpose)
    -M MiB        Use a RAM disk of MiB megabytes as build directory
    -r            Build in RELEASE mode (default: disabled), overriding project conf
    -R            Build all projects in RELEASE mode
    -s            Run static checking of source code
    -t            Tag application w/ SVN revision (default: enabled)
    -V            Bypass tool verification (ignore missing tools)
    -v            Verbose build mode
    -y [format]   Generate documentation (default: html) [html,pdf]
    -Y [format]   Generate documentation w/o building (default: html) [html,pdf]
    -x feature    Define an extra feature
    -X dir        Export the projects from SVN to a plain directory

    projects      List of space-separated projects to build
                  projects: project[ project...] with project: name[:(d|r)[gcp]]
                  If -D or -R option is specified, all default projects are
                    built, and the 'projects' list defines the build
                    customization for each specified project.
                  Suffixes:
                    :d force the project in DEBUG build
                    :r force the project in RELEASE build
                    :g force GCC toolchain
                    :c force Clang toolchain
                    :l force Clang toolchain, w/ GNU linker
                    :p force provider toolchain


Options documentation
~~~~~~~~~~~~~~~~~~~~~

.. _option_B_:

``-B``
  ignore all flags defined within the companion :ref:`build.conf <build_conf>`
  configuration file.

  The :ref:`build.conf <build_conf>` configuration file defines default values
  to build the embedded applications. To ignore this default configuration,
  use this option switches. This is likely to require that you specify some
  specific other build options to generate the embedded application.

.. _option_c:

``-c``
  clean up the build directory of the selected projects, before building them.

  The build scripts are written to first call the ``clean`` target to remove
  all generated files, then a final removal of the entire project build dir is
  performed.

  Projects that are not selected are left unaltered. However, omitting to
  specify a list of projects is equivalent to select all projects explictly:
  invoking this script without specifying a project list will clear out all
  build files for all projects.

  It is mutually exclusive with ``-C``.

.. _option_C_:

``-C``
  this option is equivalent to the ``-c`` option switch, however the script
  execution stops right after the clean up has been performed, bypassing the
  whole build stage.

  It is mutually exclusive with ``-c``.

.. _option_d:

``-d``
  build all selected projects in ``DEBUG`` mode.

  ``DEBUG`` mode usually includes a lot of debug traces, and compiler
  optimisations are disabled so that the code executes in the same order as it
  is written, which is very useful when using a debugger to step in the code.

  This is the default build mode, unless specified otherwise in the
  :ref:`build.conf <build_conf>` companion file. It overrides any
  project-specific build configuration defined in the
  :ref:`build.conf <build_conf>` configuration file.

  It is mutually exclusive with ``-D``, ``-r`` and ``-R``.

  It sets the CMake :cmake:var:`CMAKE_BUILD_TYPE` definition.

.. _option_D_:

``-D``
  build all projects in ``DEBUG`` mode unless otherwise specified. This option
  differs from the ``-d`` option: ``-d`` option switch applies ``DEBUG`` mode
  to all selected projects, projects that are not specified in the project list
  are not built. When ``-D`` is used instead, all projects are built. The
  project list can be used to specify alternate build modes for the enumerated
  projects, all other projects are built in ``DEBUG`` mode.

  For example:

  .. code-block:: sh

     build.sh -D nrf52:r

  builds all projects in ``DEBUG`` mode, but nrf52 apps that is built in
  ``RELEASE`` mode, while

  .. code-block:: sh

     build.sh -d nrf52

  only builds nrf52 apps, in ``DEBUG`` mode and ignores all other projects.

  This option is mutually exclusive with :ref:`options <option_D_>` ``-D`` and
  :ref:`release options <option_r>` ``-r`` and ``-R``.

  See the :ref:`project_specs` for details.

  This option does not override project-specific build configuration defined
  in the :ref:`build.conf <build_conf>` configuration file.

  It sets the CMake :cmake:var:`CMAKE_BUILD_TYPE` definition.

.. _option_F_:

``-F``
  force the selection of versionned tools.

  build.sh always checks for the presence of the various tools required to
  build the projects before starting the build sequence.

  Each tool is versionned, so that it is possible to define the exact version
  of each tool of the toolchain to build a project list. This is very important
  for the final product generation, in order to guarantee reproducibility of a
  production package.

  However, in development mode, using the exact version of each tool can
  rapidly become cumbersome, especially when various projects are managed on
  the same development machine.

  The default script behaviour is to accept minor variations of the defined
  tools - typically a different minor number a tool is tolerated.

  This option strictly enforces the defined versions, and early aborts if the
  exact version of each tool cannot be located.

  This is a mandatory option to use on a production environment.

  This option disables all ``BUILD*`` build mode settings that may be defined
  within the :ref:`build.conf <build_conf>` companion file.

  See also the :ref:`Environment variables <env_var>` that can be used to
  specify alternate tool versions.

  See also the ``-V`` :ref:`option switch <option_V_>`.

.. _option_j:

``-j``
  specify concurrent jobs to execute.

  This option switch tells the build system how many process to throw at
  building the selected projects.

  This allows to perform several, parallele tasks at once, hence reducing the
  overall build time.

  As a rule of thumbs, it should be set to the number of (virtual) cores of the
  host, plus two. This is the settings that gives the shortest build time.
  Using more parallel jobs than the count of cores on the host is usually
  counterproductive, as the jobs get scheduled one after another on the same
  core, and eventually reduce the overall speed.

  Typical settings are therefore: ``-j6`` for a Core i5 HT host, and ``-j10``
  on a Core i7 HT host. Your mileage may vary knowning how complex is the
  actual available count of cores depending on the CPU name.

  When Ninja_ is available, it automatically select the best job count option.

.. _option_K_:

``-K``
  build the project files (Makefile and/or Ninja files), but do not invoke
  build.

  This option enables generation of project files without actually kicking off
  a full build. It may be useful to build a single application or unit test
  without spending time building not wanted ones. In this event, a three-step
  build is required: build all projects but the application one with usual
  option switches, then build the application project with ``-K``. Finally,
  invoke make_ or Ninja_ with the specific target.

.. _option_k:

``-k``
  keep going on error.

  The default behaviour of the build system is to abort on the first fatal
  error encounted while building.

  This option is similar to its make_ counterpart, as it tries to resume the
  build when an error is encountered. This can be useful to build projects
  that are not inter-dependent if the build of one of them fails.

.. _option_l:

``-l component``
  when documentation generation is requested with :ref:`doc <option_y>` option,
  it is possible to restrict the documentation generation to the specified
  software component.

  This option may be very useful at documentation edition stage, to speed up
  documentation generation by focusing on a single or a short component list.
  This option may be repeated as many time as required to specify several
  compoment for which to generation the documentation for.

  The ``component`` syntax may be simple or specialized for a specific project.

  * simple syntax only defines the name of an existing software component. This
    filter is applied to all candidate projects: if the same component name is
    used in two projects, the documentation will be generated for both.
  * extented syntax also specify the name of the project that the component
    belongs to. In this case, the ``component`` is specified as
    ``project:component``, where project is an existing project and component
    is a valid software component of the project.

.. _option_M_:

``-M size``
  use a ``size`` MiB ramdisk as the build directory, to speed up builds and
  avoid trashing SSDs with transcient files.

  This option is only implemented for macOS for now.

.. _option_n:

``-n``
  stop after build file generation.

  The default behaviour of the script is to first create the required files to
  perform the build - that is Makefiles or Ninja build files.

  This option instructs the script to halt right after the build file
  generation, so that the generated files can be closely inspected. It is a
  debug option which is barely used in regular development.

.. _option_r:

``-r``
  build all selected projects in ``RELEASE`` mode.

  ``RELEASE`` mode removes all the traces, and enables complex compiler
  optimisations so that the code is more efficient. It becomes virtually
  impossible to debug such an optimized code, so this option should not be used
  at development stage.

  It is nevertheless a mandatory option for the final product generation.

  It is mutually exclusive with ``-d``, ``-D`` and ``-R``.

  It overrides any project-specific build configuration defined in the
  :ref:`build.conf <build_conf>` configuration file.

  It sets the CMake :cmake:var:`CMAKE_BUILD_TYPE` definition.

.. _option_R_:

``-R``
  build all projects in ``RELEASE`` mode unless otherwise specified. This
  option differs from the ``-r`` option: ``-r`` option switch applies
  ``RELEASE`` mode to all selected projects, projects that are not specified in
  the project list are not built. When ``-R`` is used instead, all projects are
  built. The project list can be used to specify alternate build modes for the
  enumerated projects, all other projects are built in ``RELEASE`` mode.

  For example:

  .. code-block:: sh

     build.sh -R nrf52:d

  builds all projects in ``RELEASE`` mode, but nrf52 apps that is built in
  ``DEBUG`` mode, while

  .. code-block:: sh

     build.sh -r nrf52

  only builds nrf52 apps, in ``RELEASE`` mode and ignores all other
  projects.

  This option is mutually exclusive with :ref:`debug options <option_d>` ``-d``,
  ``-D`` and :ref:`option <option_r>` ``-r``.

  See the :ref:`project_specs` for details.

  This option does not override project-specific build configuration defined
  in the :ref:`build.conf <build_conf>` configuration file.

  It sets the CMake :cmake:var:`CMAKE_BUILD_TYPE` definition.

.. _option_s:

``-s``
  enable static analysis of C/C++ source code.

  This option only works with projects built with LLVM/clang toolchain

  Although this level of warnings may generate false positive warning messages
  - which explains why it is not the default setting - it permits to detect
  more errors and potential flows within the source code. It performs stronger
  and more complex verifications that are not usually performed by the C
  compiler at build time.

  This option is very useful to detect issues before they actually occur
  because of a programming error. Its use is recommended on a regular basis.

  It defines the CMake :cmake:var:`XTCHECK` variable.

.. _option_t:

``-t``
  tag the project with its branch name, version control revision and build
  date.

  This option instructs the build system to generate special C/h files whose
  build object is linked with the final application / included as regular
  header file, so that the project meta information can be retrieved from the
  application itself at runtime, and reported - either as a debug trace or to
  the final user via the user interface.

  This option is enabled by default when possible, except configured otherwise
  through the :ref:`build.conf <build_conf>` companion file.

  Please note that when redistributing the source files, or exporting to
  another source control management system - such as Git, the tag files need to
  be generated first, or the final applications would not link. The build
  system is designed to report such an error with an explicit message.

  Redistributing source and tag files imposes a specific design choice for tag
  files: there are generated within the source tree, so they cannot be cleared
  out when the project is rebuilt or cleaned up. This is the only exception to
  the out-of-source build setup as described in the script
  :ref:`abstract <build_abstract>`.

  As those tag files are only generated when missing, the meta information they
  embed may become out of date. It is therefore recommened to always perform a
  clean up with the ``-c`` :ref:`option switch <option_c>` before releasing a
  tagged application.

  It defines the CMake :cmake:var:`TAG_RELEASE` variable.

.. _option_V_:

``-V``
  bypass tool verification.

  The script first attempts to verify that all required tools to build the
  embedded applications are available, before starting the actual build
  sequence. This is very useful to early detect environment and/or installation
  errors, rather than getting a hard-to-interpret error message in the middle
  of a build sequence.

  This option disables such a verification. It is not a recommended option and
  is only provided for troubleshooting purposes.

  See also the ``-F`` :ref:`option switch <option_F_>`.

.. _option_v:

``-v``
  increase verbosity.

  This option makes the build for verbose.

  It basically enables the verbose mode of all tools it invokes, so that tools
  reports detailled information about their actual execution.

  This option has been proven very useful to troubleshoot build issues, as all
  option switches of the compiler, linker and other tools are printed out.

  Be warned that this dramatically increase the volume of generated information,
  which may hide important information among the heavy load of debug info.

  It also slows down the overall build time.

  It is recommended to use the ``-j`` :ref:`option <option_j>` along with this
  mode to only run one tool after another, to ease the interpretation of the
  generated information: running several tasks at once always interleaves the
  output of different tools in the final messages, which make them hardly
  readable.

.. _option_x:

``-X <feature>``
  add one or more extra defitions for all builds.

  This feature can be used to change the way a project is built, or build it
  with a specific feature or option. Each extra feature is passed to CMake as
  a regular definition.

  Note that ``EXTRA_DEFS`` may also be defined in the environment or
  ``build.conf`` configuration file, although this is not recommended.

.. _option_X_:

``-X <dir>``
  export the project source files to a directory.

  This option is mostly useful to distribute a source tarball of the embedded
  source files to a third-party.

  It replicates the source files, including the generated meta-information
  :ref:`tag <option_t>` files to the specified directory.

  This option strips out all internal management files such as version
  management hidden directories.

  Please note that redistribution of source files to a third party is subject
  to a signed agreement and cannot be performed without a formal approval.

.. _option_y:

``-y [format]``
  enable automatic documentation generation.

  The SDK C source files contain Doxygen_ comments than can be assembled into
  HTML or PDF documents. Moreover, the Host Tools and API are documented in
  Sphinx_ format which allow to build the documentation you are reading by now.

  This option tells the build system to convert those documentation files into
  an easy to read documentation in HTML format.

  The default behavior is to ignore the documentation build step.

  If format is not specified, it defaults to HTML output. The other accepted
  option is PDF, in which case LaTeX should be installed on the host to support
  PDF output.

  It accepts the :ref:`limit <option_l>` option that restricts the list of
  components to generate the documentation for.

  .. _Doxygen: http://www.doxygen.org/
  .. _Sphinx: http://sphinx-doc.org/

.. _option_Y_:

``-Y [format]``
  enable automatic documentation generation, disabling all code compilation.

  This option generates the same doc as the :ref:`y <option_y>` option, but
  disable build of all source code.

  If format is not specified, it defaults to HTML output. The other accepted
  option is PDF, in which case LaTeX should be installed on the host to support
  PDF output.

  It also works with the :ref:`limit <option_l>` option that restrict the list
  of components to generate the documentation for.

  .. _cmake: http://www.cmake.org/
  .. _make: http://www.gnu.org/software/make/
  .. _ninja: http://martine.github.io/ninja/


.. _env_var:

Environment variables
---------------------

``USER_XTCCL_VER``
  Specify an alternate Clang/LLVM compiler version, replacing the one that is
  defined for the current ARM project.

  Ex: ``export USER_XTCCL_VER=6.1.0``

``USER_XTCCC_VER``
  Specify an alternate GCC C/C++ compiler version, replacing the one that is
  defined for the current ARM project.

  Ex: ``export USER_XTCCC_VER=8.0.0``

``USER_XTCTI_VER``
  Specify an alternate TI compiler version, replacing the one that is
  defined for the current MSP430 project.

  Ex: ``export USER_XTCTI_VER=17.0.0``

``USER_XTCBU_VER``
  Specify an alternate GNU binutils version, replacing the one that is defined
  for the current project. It is a recommened option if and only if an
  alternate compiler version is defined.

  Ex: ``export USER_XTCBU_VER=2.31``

``USER_CMAKE_VER``
  Specify an alternate CMake version, replacing the one that is defined
  for the current project.

  Ex: ``export USER_CMAKE_VER=3.0.0``

``USER_NINJA_VER``
  Specify an alternate Ninja version, replacing the one that is defined
  for the current project.

  Ex: ``export USER_NINJA_VER=1.9.0``

``USER_MAKE_VER``
  Specify an alternate GNU Make version, replacing the one that is defined
  for the current project.

  Ex: ``export USER_MAKE_VER=3.82.0``

``USER_PYTHON_VER``
  Specify an alternate Python interpreter version, replacing the one that is
  defined for the current project.

  Ex: ``export USER_PYTHON_VER=3.6.4``

``USER_DOXYGEN_VER``
  Specify an alternate Doxygen version, replacing the one that is defined
  for the current project.

  Ex: ``export USER_MAKE_VER=1.18.0``

``USER_SPHINX_VER``
  Specify an alternate Sphinx (document generation) version, replacing the one
  that is defined for the current project.

  Ex: ``export USER_SPHINX_VER=3.0.0``


.. _project_specs:

Project specifiers
------------------

The script automatically detects top-level sub-directories that contain
builable projects. A buildable project always contains a `CMakeLists.txt` file
in its own top-level directory.

Any buildable project is added to the list of project candidates.

If no project list is explicly specified on the command line, the script
selects the automatically generated project candidates as a list of project to
build. Specify one or more projects on the command line disables this default
selection and used the specified projects instead.

There are two exceptions to this rule: whenever :ref:`option <option_D_>`
``-D`` or :ref:`option <option_R_>` ``-R`` is used, the automatically generated
project list is used, and the specified project list on the command line is
used to apply project-specific build options to each enumerated project.

The available project-specific build options are enumerated below. One or more
project-specific build option(s) is selected with the `:` separator:

.. code-block:: sh

  host/bin/build.sh [-D|-R] [options] project:suffixes

where project is the selected project to which special build options should be
applied, and suffixes is a concatened list of one or more of the following
suffixes.

The ``project:suffixes`` syntax may be repeated as many time as required for
all projects that require specific build options.

The overall project syntax list is therefore a list of space-separated project
specifiers.

.. _project_suffix:

Accepted suffixes
~~~~~~~~~~~~~~~~~

  * ``:d`` force the project in DEBUG build

    * it sets the CMake :cmake:var:`CMAKE_BUILD_TYPE` definition.

  * ``:r`` force the project in RELEASE build

    * it sets the CMake :cmake:var:`CMAKE_BUILD_TYPE` definition.

  * ``:g`` force the use of the GNU C compiler / Binutils toolchain

    * it defines the CMake :cmake:var:`XTOOLCHAIN`, :cmake:var:`XCC_VER` and
      :cmake:var:`XSYSROOT` variables.

  * ``:c`` force the use of the Clang/LLVM compiler toolchain

    * it defines the CMake :cmake:var:`XTOOLCHAIN`, :cmake:var:`XCC_VER` and
      :cmake:var:`XSYSROOT` variables.

  * ``:l`` force the use of the Clang/LLVM compiler toolchain, with the GNU
    linker. LLVM linker for ARM bare metal target should still be considered
    experimental and each new LLD version usually brings regression or
    incomplete support for LD scripts.

    * it defines the CMake :cmake:var:`XTOOLCHAIN`, :cmake:var:`XCC_VER`,
      :cmake:var:`XSYSROOT` and :cmake:var:`XLD` variables.

  * ``:p`` force the use of the TI compiler (for MSP430 projects only)

    * it defines the CMake :cmake:var:`XTOOLCHAIN`, :cmake:var:`XCC_VER` and
      :cmake:var:`XSYSROOT` variables.

Note
++++

``-d`` and ``-r`` are mutually exclusive.

Other suffixes can be combined, for example:

  ``project:rc`` for ``RELEASE`` build with Clang/LLVM toolchain


Companion files
---------------

.. _build_conf:

build.conf
~~~~~~~~~~

The ``config/build.conf`` contains default definitions for the current project.

It is very useful to define a proper ``build.conf`` file as it allows to store
within the version control management system the exact configuration for the
project.

This configuration file only contains simple variable definitions using the
Shell syntax.

Supported variables
+++++++++++++++++++

``TARGET``
  Application target CPU, to select the appropriate build options.

``XTOOL``
  Application target CPU, to select the appropriate toolchain.

``BUILD``
  Force build mode: "DEBUG", "RELEASE"

.. _build_dep:

build.dep
~~~~~~~~~

The optional ``<project>/build.dep`` contains a list of dependencies that
should be built before building the current project.

The format of this file is very simple: there should be one dependency
enumerated on each line, in the desired build order.

A dependency is the name of a project, that is the directory name of the
project. All projects are immediate sub-directories of the top-level directory.

The `build.sh` script always sorts the project list - either automatically
generated or retrieved from the command line - so that all dependencies are
satisfied, prior to firing up the build sequence.

.. _cmakelists:

CMakeLists.txt
~~~~~~~~~~~~~~

To be considered as a project candidate, a directory should contain a
`CMakeLists.txt` file.

Any top-level directory missing such a file is never considered as a project
candidate, and automatically removed from the candidate list.

Dependencies
------------

In order to perform a typical build, the following tools are required:

Required dependencies
~~~~~~~~~~~~~~~~~~~~~

 * CMake (3.5+)
 * Ninja (1.6+)
 * Clang/LLVM (6.0+) for ARM targets
 * TI toolchain (16.9+) for MSP430 targets
 * Python 3.6 with additional packages (see SDK installation doc for details)

Optional dependencies
~~~~~~~~~~~~~~~~~~~~~

 * Sphinx (1.5+)
 * Doxygen (1.8.11+)
 * GNU make (3.81+)
 * GNU C and C++ compiler (7.2+ series)
 * GNU Binutils assembler, linker and miscelleanous tools (2.27+ series)

About Ninja
~~~~~~~~~~~

The default behaviour of the script is to rely on Ninja_ as a replacement of
GNU make, and instruct CMake_ to build Ninja_ build files rather than makefiles.

Ninja_ is a great alternative to make_. It is not only faster but simpler,
as it does not contain any default rules that can cause troubles and take
time to evaluate uselessly: As the build system heavily relies on CMake to
generate all - explicit - rules, most of the make_ features are useless and a
potential source of troubles.

Moreover, Ninja_ is deadly fast compare to make_ for no-op situations. This
situation arises when no source file have changed, but the build system
nevertheless needs to re-evaluate all dependencies to finally find out that
there is nothing to actually rebuilt. In these situations, Ninja_ completes
the evaluation far faster than make_ will ever do.

Please note that whatever this option, make_ is always required as eCos only
builds with make_ and cannot use Ninja_. All other projects are designed to
use Ninja_ but fallback to make_ if the former is not available.
