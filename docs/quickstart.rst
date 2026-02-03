==========
Quick Start
==========

This guide will help you write your first RevPiModIO program.

Basic Concepts
==============

RevPiModIO provides two main programming paradigms:

* **Cyclic Programming** - Execute a function at regular intervals (PLC-style)
* **Event-Driven Programming** - Register callbacks triggered by hardware changes

Both approaches use the same core objects:

* ``rpi.io`` - Access inputs and outputs by name
* ``rpi.core`` - Control LEDs, watchdog, and system status
* ``rpi.device`` - Access specific hardware devices

Hardware Configuration
======================

Before programming, configure your hardware using piCtory:

1. Access piCtory web interface on your RevPi Core module
2. Add and configure your I/O modules
3. Assign symbolic names to inputs and outputs

   * Example: ``button``, ``led``, ``temperature``
   * Good names make your code readable

4. Save configuration and activate

Your First Program
==================

Simple Input to Output
----------------------

The simplest program reads an input and controls an output:

.. code-block:: python

    import revpimodio2

    # Initialize with auto-refresh
    rpi = revpimodio2.RevPiModIO(autorefresh=True)

    # Read input and control output
    if rpi.io.button.value:
        rpi.io.led.value = True
    else:
        rpi.io.led.value = False

    # Clean up
    rpi.exit()

Cyclic Program
--------------

For continuous operation, use a cyclic loop:

.. code-block:: python

    import revpimodio2

    rpi = revpimodio2.RevPiModIO(autorefresh=True)

    def main_cycle(ct: revpimodio2.Cycletools):
        """Called every cycle (default: 20-50ms)."""

        if ct.first:
            # Initialize on first cycle
            ct.var.counter = 0
            print("Program started")

        # Main logic
        if ct.io.button.value:
            ct.io.led.value = True
        else:
            ct.io.led.value = False

        # Count button presses
        if ct.changed(ct.io.button, edge=revpimodio2.RISING):
            ct.var.counter += 1
            print(f"Button pressed {ct.var.counter} times")

        if ct.last:
            # Cleanup on exit
            print("Program stopped")

    # Run cyclic loop
    rpi.cycleloop(main_cycle)

Event-Driven Program
--------------------

For event-based operation, use callbacks:

.. code-block:: python

    import revpimodio2

    rpi = revpimodio2.RevPiModIO(autorefresh=True)

    def on_button_press(ioname, iovalue):
        """Called when button changes."""
        print(f"Button is now: {iovalue}")
        rpi.io.led.value = iovalue

    # Register event callback
    rpi.io.button.reg_event(on_button_press)

    # Handle shutdown signals
    rpi.handlesignalend()

    # Start event loop
    rpi.mainloop()

LED Control
===========

Control the RevPi status LEDs:

.. code-block:: python

    import revpimodio2

    rpi = revpimodio2.RevPiModIO(autorefresh=True)

    # Set LED colors using constants
    rpi.core.A1 = revpimodio2.GREEN  # Success
    rpi.core.A2 = revpimodio2.RED    # Error
    rpi.core.A3 = revpimodio2.OFF    # Off

    # Or control individual colors
    rpi.core.a1green.value = True
    rpi.core.a1red.value = False

    rpi.exit()

Common Patterns
===============

Initialize and Cleanup
----------------------

Always initialize variables and clean up resources:

.. code-block:: python

    def main_cycle(ct):
        if ct.first:
            # Initialize
            ct.var.state = "IDLE"
            ct.var.error_count = 0

        # Main logic here...

        if ct.last:
            # Cleanup
            ct.io.motor.value = False
            print(f"Errors: {ct.var.error_count}")

Edge Detection
--------------

Detect rising or falling edges:

.. code-block:: python

    def main_cycle(ct):
        # Detect button press (rising edge)
        if ct.changed(ct.io.button, edge=revpimodio2.RISING):
            print("Button pressed!")

        # Detect button release (falling edge)
        if ct.changed(ct.io.button, edge=revpimodio2.FALLING):
            print("Button released!")

Timers
------

Use built-in cycle-based timers:

.. code-block:: python

    def main_cycle(ct):
        # On-delay: Input must be True for 10 cycles
        ct.set_tonc("startup", 10)
        if ct.get_tonc("startup"):
            ct.io.motor.value = True

        # Pulse: Generate 5-cycle pulse
        if ct.io.trigger.value:
            ct.set_tpc("pulse", 5)
        ct.io.pulse_output.value = ct.get_tpc("pulse")

Next Steps
==========

* :doc:`basics` - Core concepts and configuration
* :doc:`cyclic_programming` - Cyclic programming patterns
* :doc:`event_programming` - Event-driven programming patterns
* :doc:`advanced` - Advanced topics and best practices
* :doc:`api/index` - API reference
