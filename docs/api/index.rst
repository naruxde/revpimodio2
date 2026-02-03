.. _api_reference:

=============
API Reference
=============

Complete API reference for RevPiModIO2 Python library.

.. contents:: Table of Contents
   :local:
   :depth: 2

Overview
========

RevPiModIO provides several main classes for programming Revolution Pi hardware:

* :class:`~revpimodio2.modio.RevPiModIO` - Main class for managing all devices and IOs
* :class:`~revpimodio2.modio.RevPiModIOSelected` - Manage specific devices only
* :class:`~revpimodio2.modio.RevPiModIODriver` - Write data to virtual device inputs
* :class:`~revpimodio2.io.IOList` - Container for accessing IOs
* :class:`~revpimodio2.io.IOBase` - Base class for all IO objects
* :class:`~revpimodio2.helper.Cycletools` - Toolkit for cyclic programming
* :class:`~revpimodio2.helper.EventCallback` - Event handler class

Quick Examples
==============

Basic Usage
-----------

.. code-block:: python

    import revpimodio2

    # Initialize
    rpi = revpimodio2.RevPiModIO(autorefresh=True)

    # Read input and control output
    if rpi.io.button.value:
        rpi.io.led.value = True

    # Cleanup
    rpi.exit()

Cyclic Programming
------------------

.. code-block:: python

    import revpimodio2

    rpi = revpimodio2.RevPiModIO(autorefresh=True)

    def main_cycle(ct: revpimodio2.Cycletools):
        if ct.first:
            ct.var.counter = 0

        if ct.changed(ct.io.sensor):
            ct.var.counter += 1

    rpi.cycleloop(main_cycle)

Event-Driven Programming
------------------------

.. code-block:: python

    import revpimodio2

    rpi = revpimodio2.RevPiModIO(autorefresh=True)

    def on_change(ioname, iovalue):
        print(f"{ioname} = {iovalue}")

    rpi.io.button.reg_event(on_change)
    rpi.handlesignalend()
    rpi.mainloop()

Constants
=========

Edge Detection
--------------

.. py:data:: revpimodio2.RISING
   :type: int

   Detect low-to-high transitions

.. py:data:: revpimodio2.FALLING
   :type: int

   Detect high-to-low transitions

.. py:data:: revpimodio2.BOTH
   :type: int

   Detect any transition

LED Colors
----------

.. py:data:: revpimodio2.OFF
   :type: int

   LED off

.. py:data:: revpimodio2.GREEN
   :type: int

   Green LED

.. py:data:: revpimodio2.RED
   :type: int

   Red LED

IO Types
--------

.. py:data:: INP
   :type: int
   :value: 300

   Input type

.. py:data:: OUT
   :type: int
   :value: 301

   Output type

.. py:data:: MEM
   :type: int
   :value: 302

   Memory type

See Also
========

* :doc:`../installation` - Installation guide
* :doc:`../quickstart` - Quick start guide
* :doc:`../basics` - Core concepts
* :doc:`../cyclic_programming` - Cyclic programming patterns
* :doc:`../event_programming` - Event-driven programming patterns
* :doc:`../advanced` - Advanced topics
