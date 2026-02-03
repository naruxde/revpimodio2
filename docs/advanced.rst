========
Advanced
========

Advanced features, patterns, and best practices for RevPiModIO.

.. contents:: Contents
   :local:
   :depth: 2

Custom IOs (Gateway Modules)
=============================

Gateway modules (ModbusTCP, Profinet, etc.) allow defining custom IOs dynamically.

Understanding Gateway IOs
--------------------------

Gateway modules provide raw memory regions that you can map to custom IOs with specific data types and addresses.

Defining Custom IOs
-------------------

Use the :py:meth:`~revpimodio2.io.MemIO.replace_io` method to define custom IOs on gateway modules.

Gateway modules provide generic IOs (like ``Input_1``, ``Output_1``, etc.) that you can replace with custom definitions:

.. code-block:: python

    import revpimodio2

    rpi = revpimodio2.RevPiModIO(autorefresh=True)

    # Replace a gateway IO with custom definition
    # Gateway IOs have default names like Input_1, Output_1, etc.
    rpi.io.Input_1.replace_io(
        "temperature",     # New IO name
        "h",              # struct format: signed short
        defaultvalue=0    # Default value
    )

    # Use the custom IO by its new name
    temp = rpi.io.temperature.value / 10.0  # Scale to degrees
    print(f"Temperature: {temp}°C")

    rpi.exit()

**Parameters:**

* ``name`` - Name for the new IO (will be accessible via ``rpi.io.name``)
* ``frm`` - Struct format character (see `format codes <https://docs.python.org/3/library/struct.html#format-characters>`_ below)
* ``defaultvalue`` - Optional: Default value for the IO
* ``byteorder`` - Optional: Byte order (``'little'`` or ``'big'``), default is ``'little'``
* ``bit`` - Optional: Bit position for boolean IOs (0-7)
* ``event`` - Optional: Register event callback on creation
* ``delay`` - Optional: Event debounce delay in milliseconds
* ``edge`` - Optional: Event edge trigger (RISING, FALLING, or BOTH)

**Note:** The memory address is inherited from the IO being replaced (e.g., ``Input_1``). The new IO uses the same address in the process image.

Struct Format Codes
-------------------

Common format codes for ``replace_io`` (see `Python struct format characters <https://docs.python.org/3/library/struct.html#format-characters>`_ for complete reference):

* ``'b'`` - signed byte (-128 to 127)
* ``'B'`` - unsigned byte (0 to 255)
* ``'h'`` - signed short (-32768 to 32767)
* ``'H'`` - unsigned short (0 to 65535)
* ``'i'`` - signed int (-2147483648 to 2147483647)
* ``'I'`` - unsigned int (0 to 4294967295)
* ``'f'`` - float (32-bit)

Multiple Custom IOs
-------------------

Define multiple custom IOs programmatically by replacing generic gateway IOs:

.. code-block:: python

    rpi = revpimodio2.RevPiModIO(autorefresh=True)

    # Replace multiple gateway IOs with custom definitions
    # Assuming a gateway module with Input_1, Input_2, Output_1, Output_2
    rpi.io.Input_1.replace_io("temperature", "h", defaultvalue=0)
    rpi.io.Input_2.replace_io("humidity", "h", defaultvalue=0)
    rpi.io.Output_1.replace_io("setpoint", "h", defaultvalue=700)
    rpi.io.Output_2.replace_io("control_word", "H", defaultvalue=0)

    # Use all custom IOs by their new names
    temp = rpi.io.temperature.value / 10.0
    humidity = rpi.io.humidity.value / 10.0
    print(f"Temp: {temp}°C, Humidity: {humidity}%")

    # Write to output registers
    rpi.io.setpoint.value = 750  # 75.0°C
    rpi.io.control_word.value = 0x0001  # Enable bit

    rpi.exit()

Using Configuration Files
--------------------------

For complex IO configurations, use the ``replace_io_file`` parameter to load custom IOs from a file:

.. code-block:: python

    # Load custom IOs from configuration file
    rpi = revpimodio2.RevPiModIO(
        autorefresh=True,
        replace_io_file="replace_ios.conf"
    )

    # Custom IOs are now available
    temp = rpi.io.temperature.value / 10.0
    print(f"Temperature: {temp}°C")

    rpi.exit()

**Configuration File Format:**

Create an INI-style configuration file (``replace_ios.conf``):

.. code-block:: ini

    [temperature]
    replace = Input_1
    frm = h
    defaultvalue = 0

    [humidity]
    replace = Input_2
    frm = h
    defaultvalue = 0

    [setpoint]
    replace = Output_1
    frm = h
    defaultvalue = 700

    [control_word]
    replace = Output_2
    frm = H
    byteorder = big

**Configuration Parameters:**

* ``replace`` - Name of the gateway IO to replace (required)
* ``frm`` - Struct format character (required)
* ``bit`` - Bit position for boolean IOs (0-7)
* ``byteorder`` - Byte order: ``little`` or ``big`` (default: ``little``)
* ``wordorder`` - Word order for multi-word values
* ``defaultvalue`` - Default value for the IO
* ``bmk`` - Internal designation/bookmark
* ``export`` - Export flag for RevPiPyLoad/RevPiPyControl

**Exporting Configuration:**

Export your current custom IOs to a file:

.. code-block:: python

    rpi = revpimodio2.RevPiModIO(autorefresh=True)

    # Define custom IOs by replacing gateway IOs
    rpi.io.Input_1.replace_io("temperature", "h", defaultvalue=0)
    rpi.io.Input_2.replace_io("humidity", "h", defaultvalue=0)

    # Export to configuration file
    rpi.export_replaced_ios("my_config.conf")

    rpi.exit()

This is useful for:

* Sharing IO configurations across multiple programs
* Integration with RevPiPyLoad and RevPiPyControl
* Version control of IO definitions
* Declarative IO configuration

Watchdog Management
===================

The hardware watchdog monitors your program and resets the system if it stops responding.

How the Watchdog Works
-----------------------

The watchdog requires periodic toggling. If not toggled within the timeout period, the system resets.

**Important:** Only enable the watchdog when your program logic is working correctly.

Cyclic Watchdog Toggle
-----------------------

.. code-block:: python

    import revpimodio2

    rpi = revpimodio2.RevPiModIO(autorefresh=True)

    def main_cycle(ct):
        # Toggle every 10 cycles (200ms @ 20ms)
        if ct.flank10c:
            ct.core.wd_toggle()

        # Your control logic
        ct.io.output.value = ct.io.input.value

    rpi.cycleloop(main_cycle)

Event-Driven Watchdog Toggle
-----------------------------

.. code-block:: python

    import revpimodio2

    rpi = revpimodio2.RevPiModIO(autorefresh=True)

    def toggle_wd(ioname, iovalue):
        """Toggle watchdog every 500ms."""
        rpi.core.wd_toggle()

    # Register timer event for watchdog
    rpi.core.wd.reg_timerevent(toggle_wd, 500, prefire=True)

    # Your event handlers
    def on_button(ioname, iovalue):
        rpi.io.led.value = iovalue

    rpi.io.button.reg_event(on_button)

    rpi.handlesignalend()
    rpi.mainloop()

Conditional Watchdog
--------------------

Enable watchdog only when system is operational:

.. code-block:: python

    def machine_with_watchdog(ct):
        if ct.first:
            ct.var.state = "IDLE"
            ct.var.watchdog_enabled = False

        # Enable watchdog only in RUNNING state
        if ct.var.state == "RUNNING":
            if not ct.var.watchdog_enabled:
                ct.var.watchdog_enabled = True
                print("Watchdog enabled")

            # Toggle watchdog
            if ct.flank10c:
                ct.core.wd_toggle()

        else:
            ct.var.watchdog_enabled = False

        # State machine logic
        if ct.var.state == "IDLE":
            if ct.io.start_button.value:
                ct.var.state = "RUNNING"

        elif ct.var.state == "RUNNING":
            ct.io.motor.value = True
            if ct.io.stop_button.value:
                ct.var.state = "IDLE"

    rpi = revpimodio2.RevPiModIO(autorefresh=True)
    rpi.cycleloop(machine_with_watchdog)

Combining Paradigms
===================

Combine cyclic and event-driven programming for optimal results.

Cyclic Control with Event UI
-----------------------------

Use cyclic for time-critical control, events for user interface:

.. code-block:: python

    import revpimodio2
    import threading

    rpi = revpimodio2.RevPiModIO(autorefresh=True)

    def cyclic_control(ct: revpimodio2.Cycletools):
        """Fast control loop."""
        if ct.first:
            ct.var.setpoint = 50.0
            ct.var.running = False

        if ct.var.running:
            # Fast control logic
            error = ct.var.setpoint - ct.io.sensor.value
            if error > 5:
                ct.io.actuator.value = True
            elif error < -5:
                ct.io.actuator.value = False

    def on_setpoint_change(ioname, iovalue):
        """Event handler for user setpoint changes."""
        print(f"New setpoint: {iovalue}")
        # Access ct.var from event requires thread-safe approach
        # In practice, use shared data structure or message queue

    def on_start(ioname, iovalue):
        print("System started")

    def on_stop(ioname, iovalue):
        print("System stopped")

    # Register user events
    rpi.io.start_button.reg_event(on_start, edge=revpimodio2.RISING)
    rpi.io.stop_button.reg_event(on_stop, edge=revpimodio2.RISING)
    rpi.io.setpoint_input.reg_event(on_setpoint_change, delay=100)

    # Run cyclic loop in background
    threading.Thread(
        target=lambda: rpi.cycleloop(cyclic_control),
        daemon=True
    ).start()

    # Run event loop in main thread
    rpi.handlesignalend()
    rpi.mainloop()

Event Triggers with Cyclic Processing
--------------------------------------

Use events to trigger actions, cyclic for processing:

.. code-block:: python

    import revpimodio2

    rpi = revpimodio2.RevPiModIO(autorefresh=True)

    def cyclic_processor(ct):
        """Process work queue."""
        if ct.first:
            ct.var.work_queue = []

        # Process queued work
        if ct.var.work_queue:
            item = ct.var.work_queue.pop(0)
            process_item(item)

    def on_new_item(ioname, iovalue):
        """Queue work from events."""
        # Note: Accessing ct.var from events requires synchronization
        # This is a simplified example
        print(f"New item queued from {ioname}")

    rpi.io.trigger1.reg_event(on_new_item, edge=revpimodio2.RISING)
    rpi.io.trigger2.reg_event(on_new_item, edge=revpimodio2.RISING)

    rpi.cycleloop(cyclic_processor)

Performance Optimization
========================

Keep Cycle Logic Fast
---------------------

Minimize processing time in each cycle:

.. code-block:: python

    def optimized_cycle(ct):
        # Good: Heavy work only when needed
        if ct.flank100c:
            expensive_calculation()

        # Good: Keep cycle logic minimal
        ct.io.output.value = ct.io.input.value

        # Bad: Don't do this every cycle
        # expensive_calculation()  # 100ms processing!

**Guidelines:**

* Keep cycle time ≥20ms for stability
* Avoid blocking operations (network, file I/O)
* Use flank flags for expensive operations
* Profile your cycle function if experiencing timing issues

Choose Appropriate Cycle Time
------------------------------

Match cycle time to application requirements:

.. code-block:: python

    # Fast control (motion, high-speed counting)
    rpi.cycletime = 20  # 50 Hz

    # Normal control (most applications)
    rpi.cycletime = 50  # 20 Hz

    # Slow monitoring (temperature, status)
    rpi.cycletime = 100  # 10 Hz

**Trade-offs:**

* Faster = Higher CPU usage, better responsiveness
* Slower = Lower CPU usage, adequate for most tasks

Minimize Event Callbacks
-------------------------

Keep event callbacks lightweight:

.. code-block:: python

    # Good: Fast callback
    def good_callback(ioname, iovalue):
        rpi.io.output.value = iovalue

    # Poor: Slow callback blocks event loop
    def poor_callback(ioname, iovalue):
        time.sleep(1)  # Blocks!
        complex_calculation()  # Slow!
        rpi.io.output.value = iovalue

    # Better: Use threaded events for slow work
    def threaded_callback(eventcallback):
        complex_calculation()
        rpi.io.output.value = result

    rpi.io.trigger.reg_event(threaded_callback, as_thread=True)

Error Handling
==============

Graceful Error Recovery
-----------------------

Always implement safe failure modes:

.. code-block:: python

    def safe_cycle(ct):
        try:
            value = ct.io.sensor.value
            result = process(value)
            ct.io.output.value = result
        except ValueError as e:
            print(f"Sensor error: {e}")
            ct.io.output.value = 0  # Safe default
        except Exception as e:
            print(f"Unexpected error: {e}")
            ct.io.output.value = False  # Safe state

Resource Cleanup
----------------

Always clean up resources:

.. code-block:: python

    import revpimodio2

    rpi = revpimodio2.RevPiModIO(autorefresh=True)

    try:
        # Your program logic
        rpi.cycleloop(main_cycle)
    except KeyboardInterrupt:
        print("Interrupted by user")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        # Always clean up
        rpi.setdefaultvalues()  # Reset outputs to defaults
        rpi.exit()

Monitor I/O Errors
------------------

Track and handle I/O errors:

.. code-block:: python

    rpi = revpimodio2.RevPiModIO(autorefresh=True)
    rpi.maxioerrors = 10  # Exception after 10 errors

    def main_cycle(ct):
        # Check error count periodically
        if ct.flank20c:
            if rpi.ioerrors > 5:
                print(f"Warning: {rpi.ioerrors} I/O errors detected")
                ct.io.warning_led.value = True

        # Normal logic
        ct.io.output.value = ct.io.input.value

    try:
        rpi.cycleloop(main_cycle)
    except RuntimeError as e:
        print(f"I/O error threshold exceeded: {e}")

Best Practices
==============

Naming Conventions
------------------

Use descriptive IO names in piCtory:

.. code-block:: python

    # Good - Clear intent
    if rpi.io.emergency_stop.value:
        rpi.io.motor.value = False
        rpi.io.alarm.value = True

    # Poor - Generic names
    if rpi.io.I_15.value:
        rpi.io.O_3.value = False
        rpi.io.O_7.value = True

Code Organization
-----------------

Structure your code for maintainability:

.. code-block:: python

    import revpimodio2

    # Constants
    TEMP_HIGH_THRESHOLD = 75
    TEMP_LOW_THRESHOLD = 65

    # Initialize
    rpi = revpimodio2.RevPiModIO(autorefresh=True)

    def initialize(ct):
        """Initialize system state."""
        ct.var.cooling_active = False
        ct.var.alarm_active = False
        ct.io.motor.value = False

    def monitor_temperature(ct):
        """Temperature monitoring logic."""
        temp = ct.io.temperature.value

        if temp > TEMP_HIGH_THRESHOLD:
            ct.io.cooling.value = True
            ct.var.cooling_active = True

        if temp < TEMP_LOW_THRESHOLD:
            ct.io.cooling.value = False
            ct.var.cooling_active = False

    def main_cycle(ct):
        """Main control loop."""
        if ct.first:
            initialize(ct)

        monitor_temperature(ct)

        if ct.last:
            ct.io.cooling.value = False

    # Run
    try:
        rpi.cycleloop(main_cycle)
    finally:
        rpi.exit()

Documentation
-------------

Document complex logic:

.. code-block:: python

    def control_cycle(ct):
        """Control cycle for temperature management.

        State machine:
        - IDLE: Waiting for start
        - HEATING: Active heating to setpoint
        - COOLING: Active cooling from overshoot
        - ERROR: Fault condition

        Hysteresis: ±5°C around setpoint
        """
        if ct.first:
            ct.var.state = "IDLE"
            ct.var.setpoint = 70.0

        # State machine implementation
        # ...

Testing
-------

Test your code thoroughly:

.. code-block:: python

    def test_temperature_control(ct):
        """Test temperature control logic."""

        if ct.first:
            ct.var.cooling_active = False
            ct.var.test_temp = 20.0

        # Simulate temperature increase
        if ct.var.test_temp < 80:
            ct.var.test_temp += 0.5

        # Test control logic
        temp = ct.var.test_temp

        if temp > 75 and not ct.var.cooling_active:
            assert ct.io.cooling.value == True
            ct.var.cooling_active = True

        if temp < 65 and ct.var.cooling_active:
            assert ct.io.cooling.value == False
            ct.var.cooling_active = False

Logging
-------

Implement proper logging:

.. code-block:: python

    import logging
    from datetime import datetime

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    def main_cycle(ct):
        if ct.first:
            logging.info("System started")
            ct.var.error_count = 0

        # Log errors
        if ct.io.error_sensor.value:
            ct.var.error_count += 1
            logging.error(f"Error detected: {ct.var.error_count}")

        # Log status periodically
        if ct.flank100c:
            logging.info(f"Temperature: {ct.io.temperature.value}°C")

        if ct.last:
            logging.info("System stopped")

Security Considerations
=======================

Validate External Input
-----------------------

Always validate external inputs:

.. code-block:: python

    def on_setpoint_change(ioname, iovalue):
        """Validate setpoint range."""
        if 0 <= iovalue <= 100:
            rpi.io.setpoint.value = iovalue
        else:
            print(f"Invalid setpoint: {iovalue}")
            rpi.io.error_led.value = True

Fail-Safe Defaults
------------------

Use safe defaults for critical outputs:

.. code-block:: python

    def main_cycle(ct):
        if ct.first:
            # Safe defaults
            ct.io.motor.value = False
            ct.io.heater.value = False
            ct.io.valve.value = False

        try:
            # Control logic
            control_logic(ct)
        except Exception as e:
            # Revert to safe state on error
            ct.io.motor.value = False
            ct.io.heater.value = False

See Also
========

* :doc:`basics` - Core concepts and configuration
* :doc:`cyclic_programming` - Cyclic programming patterns
* :doc:`event_programming` - Event-driven programming patterns
* :doc:`api/index` - API reference
