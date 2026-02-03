======
Basics
======

Core concepts and fundamental usage of RevPiModIO.

.. contents:: Contents
   :local:
   :depth: 2

Programming Paradigms
=====================

RevPiModIO supports two complementary programming approaches:

**Cyclic Programming** - Execute a function at regular intervals, similar to PLC programming.

* Best for deterministic timing, state machines, and time-critical control
* Runs your function every cycle (typically 20-50ms)
* See :doc:`cyclic_programming` for details

**Event-Driven Programming** - Register callbacks triggered by hardware state changes.

* Best for user interactions, sporadic events, and system integration
* Consumes CPU only when events occur
* See :doc:`event_programming` for details

Both approaches can be combined in a single application. See :doc:`advanced` for examples.

Getting Started
===============

Basic Instantiation
-------------------

Create a RevPiModIO instance to access your hardware:

.. code-block:: python

    import revpimodio2

    rpi = revpimodio2.RevPiModIO(autorefresh=True)

    # Your code here

    rpi.exit()

Configuration Parameters
------------------------

.. code-block:: python

    rpi = revpimodio2.RevPiModIO(
        autorefresh=True,    # Auto-sync process image (recommended)
        monitoring=False,    # Read-only mode
        syncoutputs=True,    # Load output values on init
        debug=False          # Enable debug messages
    )

**autorefresh** - Automatically reads inputs and writes outputs. Set to ``True`` for most applications.

**monitoring** - Read-only mode. Use when monitoring without controlling hardware.

**syncoutputs** - Load current output values on startup. Prevents outputs from resetting.

**debug** - Enable debug logging for troubleshooting.

Cycle Timing
------------

Default update rates depend on your hardware:

* **Core 1**: 40ms (25Hz)
* **Core3/Connect**: 20ms (50Hz)
* **NetIO**: 50ms (20Hz)

Adjust cycle time to match your needs:

.. code-block:: python

    rpi = revpimodio2.RevPiModIO(autorefresh=True)
    rpi.cycletime = 100  # Set to 100ms

**Important:** Faster cycle times consume more CPU. Choose the slowest cycle time that meets your requirements.

Error Handling
--------------

Configure I/O error threshold:

.. code-block:: python

    rpi.maxioerrors = 10  # Raise exception after 10 errors

    # Check error count
    if rpi.ioerrors > 5:
        print("Warning: I/O errors detected")

Core Objects
============

rpi.io - Input/Output Access
-----------------------------

Access all configured IOs from piCtory:

.. code-block:: python

    # Direct attribute access
    value = rpi.io.button.value
    rpi.io.led.value = True

    # String-based access
    rpi.io["button"].value

    # Check existence
    if "sensor" in rpi.io:
        print(rpi.io.sensor.value)

    # Iterate all IOs
    for io in rpi.io:
        print(f"{io.name}: {io.value}")

IO Properties
~~~~~~~~~~~~~

Each IO object has these properties:

* ``.name`` - IO name from piCtory
* ``.value`` - Current value (read/write)
* ``.address`` - Byte address in process image
* ``.type`` - IO type (INPUT=300, OUTPUT=301, MEMORY=302)
* ``.defaultvalue`` - Default value from piCtory

rpi.core - System Control
--------------------------

Access Revolution Pi system features:

LED Control
~~~~~~~~~~~

.. code-block:: python

    # Using constants
    rpi.core.A1 = revpimodio2.GREEN
    rpi.core.A2 = revpimodio2.RED
    rpi.core.A3 = revpimodio2.OFF

    # Individual colors
    rpi.core.a1green.value = True
    rpi.core.a1red.value = False

System Status
~~~~~~~~~~~~~

.. code-block:: python

    # CPU information
    temp = rpi.core.temperature.value
    freq = rpi.core.frequency.value

    # piBridge status
    cycle_time = rpi.core.iocycle.value
    errors = rpi.core.ioerrorcount.value

Watchdog
~~~~~~~~

.. code-block:: python

    # Toggle watchdog
    rpi.core.wd_toggle()

    # Watchdog IO object
    rpi.core.wd.value = True

See :doc:`advanced` for complete watchdog management examples.

rpi.device - Device Access
---------------------------

Access specific hardware devices:

.. code-block:: python

    # By name
    dio = rpi.device.DIO_Module_1

    # By position
    first = rpi.device[0]

    # Iterate
    for device in rpi.device:
        print(device.name)

Signal Handling
===============

Graceful Shutdown
-----------------

Handle SIGINT and SIGTERM for clean program termination:

.. code-block:: python

    rpi = revpimodio2.RevPiModIO(autorefresh=True)

    # Enable signal handling
    rpi.handlesignalend()

    # Run main loop
    rpi.mainloop()

Custom Signal Handler
---------------------

Implement custom cleanup logic:

.. code-block:: python

    def cleanup(signum, frame):
        print("Shutting down...")
        rpi.setdefaultvalues()
        rpi.exit()

    rpi.handlesignalend(cleanup)
    rpi.mainloop()

Simple Examples
===============

Read Input, Control Output
---------------------------

.. code-block:: python

    import revpimodio2

    rpi = revpimodio2.RevPiModIO(autorefresh=True)

    # Read input and control output
    if rpi.io.button.value:
        rpi.io.led.value = True
    else:
        rpi.io.led.value = False

    rpi.exit()

LED Control
-----------

.. code-block:: python

    import revpimodio2

    rpi = revpimodio2.RevPiModIO(autorefresh=True)

    # Control status LEDs
    rpi.core.A1 = revpimodio2.GREEN
    rpi.core.A2 = revpimodio2.RED

    rpi.exit()

Iterate All IOs
---------------

.. code-block:: python

    import revpimodio2

    rpi = revpimodio2.RevPiModIO(autorefresh=True)

    # Print all IOs and their values
    for io in rpi.io:
        print(f"{io.name}: {io.value}")

    rpi.exit()

Best Practices
==============

Use Descriptive IO Names
-------------------------

Configure descriptive names in piCtory:

.. code-block:: python

    # Good - Clear intent
    if rpi.io.emergency_stop.value:
        rpi.io.motor.value = False

    # Poor - Generic names
    if rpi.io.I_15.value:
        rpi.io.O_3.value = False

Always Clean Up
---------------

Always call ``rpi.exit()`` to clean up resources:

.. code-block:: python

    rpi = revpimodio2.RevPiModIO(autorefresh=True)

    try:
        # Your code here
        pass
    finally:
        rpi.exit()

Check IO Existence
------------------

Verify IOs exist before accessing:

.. code-block:: python

    if "optional_sensor" in rpi.io:
        value = rpi.io.optional_sensor.value
    else:
        print("Sensor not configured")

See Also
========

* :doc:`cyclic_programming` - Cyclic programming patterns
* :doc:`event_programming` - Event-driven programming patterns
* :doc:`advanced` - Advanced topics and best practices
* :doc:`api/index` - API reference
