.. las4windows documentation master file.

The las4windows docs
====================

*las4windows* is forked from [GCS_scripts by Kenny Larrieu](https://github.com/klarrieu). The original code is designed for *Python2* and the commercial ``arcpy`` library. The tweaked codes of *las4windows* run with Python 3.8 and work without ``arcpy``. This repository only uses the GUI for lidar processing with `LASTools <https://rapidlasso.com/lastools/>`_.

Because *LASTools* is proprietary, its executables can hardly be run on Linux or other UNIX-based systems. This is why *las4windows* is a *Windows*-only (*nomen est omen*).

## Prerequisites


*LASTools* is used for LiDAR Data Processing and can be downloaded `here <https://rapidlasso.com/lastools/>`_.

Python 3.x dependencies are provided with ``requirements.txt`` (most modern IDEs will provide to auto-install the packages listed in ``requirements.txt``). Otherwise, make sure to install the following libraries in the *Python3.x* environment:

   * numpy
   * scipy
   * tkinter
   * pandas


Code Documentation
==================


The GUI script
~~~~~~~~~~~~~~
.. automodule:: LiDAR_processing_GUI
   :members:

File and processing functions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
.. automodule:: file_functions
   :members:


Indices and tables
==================

* :ref:``genindex``
* :ref:``modindex``
* :ref:``search``



