==================
RevPiModIO Classes
==================

Main classes for managing Revolution Pi hardware.

.. currentmodule:: revpimodio2.modio

RevPiModIO
==========

.. autoclass:: RevPiModIO
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__

   Main class for managing all devices and IOs from the piCtory configuration.

   This class manages the complete piCtory configuration and loads all devices
   and IOs. It handles exclusive management of the process image and ensures
   data synchronization.

   **Constructor Parameters:**

   :param autorefresh: Automatically sync process image (recommended: True)
   :type autorefresh: bool
   :param monitoring: Read-only mode for supervision (no writes)
   :type monitoring: bool
   :param syncoutputs: Load current output values on initialization
   :type syncoutputs: bool
   :param debug: Enable detailed error messages and logging
   :type debug: bool

   **Key Attributes:**



      Access to all configured inputs/outputs



      Access to RevPi Core values (LEDs, status)



      Access to specific devices by name



      Update frequency in milliseconds



      Threading event for clean shutdown



      Count of read/write failures



      Exception threshold (0 = disabled)

   **Example:**

   .. code-block:: python

       import revpimodio2

       # Initialize with auto-refresh
       rpi = revpimodio2.RevPiModIO(autorefresh=True)

       # Access IOs
       if rpi.io.button.value:
           rpi.io.led.value = True

       # Clean shutdown
       rpi.exit()

Loop Execution Methods
----------------------


Data Synchronization Methods
-----------------------------


Utility Methods
---------------


RevPiModIOSelected
==================

.. autoclass:: RevPiModIOSelected
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__

   Manage only specific devices from the piCtory configuration.

   Use this class when you only need to control specific devices instead of
   loading the entire configuration.

   **Example:**

   .. code-block:: python

       # Manage only specific devices
       rpi = revpimodio2.RevPiModIOSelected("DIO_Module_1", "AIO_Module_1")

RevPiModIODriver
================

.. autoclass:: RevPiModIODriver
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__

   Write data to virtual device inputs for driver development.

   **Example:**

   .. code-block:: python

       # Create driver for virtual device
       driver = revpimodio2.RevPiModIODriver("VirtualDevice")

DevSelect
=========

.. autoclass:: DevSelect
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__

   Customized search filter for RevPiModIOSelected.
