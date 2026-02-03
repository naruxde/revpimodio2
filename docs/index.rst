====================================
Welcome to RevPiModIO Documentation!
====================================

RevPiModIO is a Python3 module for programming Revolution Pi hardware from KUNBUS GmbH.
It provides easy access to all devices and IOs from the piCtory configuration, supporting
both cyclic (PLC-style) and event-driven programming paradigms.

.. note::
   **New to RevPiModIO?** Start with :doc:`installation` and :doc:`quickstart`.

Key Features
============

* **Dual Programming Models**: Cyclic (PLC-style) and event-driven approaches
* **Direct Hardware Access**: Simple Python interface to all I/O devices
* **Automatic Configuration**: Loads piCtory device configuration
* **Event System**: Callbacks for value changes and timer events
* **Open Source**: LGPLv2 license, no licensing fees

Quick Example
=============

**Cyclic Programming**::

    import revpimodio2
    rpi = revpimodio2.RevPiModIO(autorefresh=True)

    def main(ct):
        if ct.io.button.value:
            ct.io.led.value = True

    rpi.cycleloop(main)

**Event-Driven Programming**::

    import revpimodio2
    rpi = revpimodio2.RevPiModIO(autorefresh=True)

    def on_change(ioname, iovalue):
        print(f"{ioname} = {iovalue}")

    rpi.io.button.reg_event(on_change)
    rpi.handlesignalend()
    rpi.mainloop()

Documentation
=============

.. toctree::
   :maxdepth: 2
   :caption: Getting Started

   installation
   quickstart

.. toctree::
   :maxdepth: 2
   :caption: User Guide

   basics
   cyclic_programming
   event_programming
   advanced

.. toctree::
   :maxdepth: 3
   :caption: API Reference

   api/index
   api/revpimodio
   api/io
   api/helper
   api/device

External Resources
==================

* **Official Website**: `revpimodio.org <https://revpimodio.org>`_
* **GitHub Repository**: `github.com/naruxde/ <https://github.com/naruxde/>`_
* **Discussion Forum**: `revpimodio.org/diskussionsforum/ <https://revpimodio.org/diskussionsforum/>`_
* **Revolution Pi Hardware**: `revolution.kunbus.com <https://revolution.kunbus.com>`_

Indices and Tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
