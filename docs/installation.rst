============
Installation
============

System Requirements
===================

* Python 3.7 or higher
* Revolution Pi hardware (Core, Core3, Connect, Compact, Flat)
* piCtory configuration tool

Prerequisites
=============

User Permissions
----------------

On Bookworm images, users must belong to the ``picontrol`` group::

    sudo usermod -a -G picontrol username

Log out and log back in for the group change to take effect.

Installing RevPiModIO
=====================

Using pip
---------

Install from PyPI::

    pip install revpimodio2

From Source
-----------

Clone the repository and install::

    git clone https://github.com/naruxde/revpimodio2.git
    cd revpimodio2
    pip install .

Verify Installation
===================

Test the installation::

    python3 -c "import revpimodio2; print(revpimodio2.__version__)"

Optional Components
===================

RevPiPyLoad
-----------

For advanced features like XML-RPC server and MQTT integration::

    sudo apt-get update
    sudo apt-get install revpipyload

Configure XML-RPC Server
~~~~~~~~~~~~~~~~~~~~~~~~~

Edit ``/etc/revpipyload/revpipyload.conf``::

    [XMLRPC]
    xmlrpc = 1

Configure access permissions in ``/etc/revpipyload/aclxmlrpc.conf``, then restart::

    sudo service revpipyload restart

RevPi Commander
---------------

RevPi Commander provides a GUI for testing I/O without programming:

1. Download from `revpimodio.org <https://revpimodio.org/quellen/revpicommander/>`_
2. Configure connection via File → Connections with your RevPi's IP address (port: 55123)
3. Use "PLC watch mode" to monitor sensors and control outputs

Next Steps
==========

After installation, proceed to :doc:`quickstart` to write your first program.
