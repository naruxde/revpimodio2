==================
Cyclic Programming
==================

Cyclic programming executes a function at regular intervals, similar to PLC programming.

.. contents:: Contents
   :local:
   :depth: 2

When to Use Cyclic Programming
===============================

**Cyclic programming is ideal for:**

* Deterministic timing requirements
* Traditional PLC-style logic
* State machines
* Time-critical control
* Continuous monitoring and control

**Advantages:**

* Predictable timing
* Simple mental model
* Easy to reason about program flow
* Natural for control systems

**Considerations:**

* Consumes CPU even when idle
* Cycle time affects responsiveness
* Must keep cycle logic fast

Basic Structure
===============

Simple Cycle Loop
-----------------

.. code-block:: python

    import revpimodio2

    rpi = revpimodio2.RevPiModIO(autorefresh=True)

    def main_cycle(ct: revpimodio2.Cycletools):
        """Execute each cycle."""
        if ct.io.start_button.value:
            ct.io.motor.value = True
        if ct.io.stop_button.value:
            ct.io.motor.value = False

    rpi.cycleloop(main_cycle)

The ``main_cycle`` function is called repeatedly at the configured cycle time (typically 20-50ms).

Understanding Cycle Time
-------------------------

The cycle time determines execution frequency:

* **Core 1**: 40ms (25 Hz)
* **Core3/Connect**: 20ms (50 Hz)
* **NetIO**: 50ms (20 Hz)

Adjust cycle time to match your needs:

.. code-block:: python

    rpi = revpimodio2.RevPiModIO(autorefresh=True)
    rpi.cycletime = 100  # 100ms = 10 Hz

**Important:** Faster cycle times consume more CPU. Choose the slowest cycle time that meets your requirements.

Cycletools Object
=================

The ``Cycletools`` object is passed to your cycle function, providing access to:

* ``ct.io`` - All IOs
* ``ct.core`` - System control
* ``ct.device`` - Device access
* ``ct.var`` - Persistent variables
* Lifecycle flags (``first``, ``last``)
* Timing flags (``flag5c``, ``flank10c``, etc.)
* Timer functions (``set_tonc``, ``get_tofc``, etc.)
* Change detection (``changed``)

Initialization and Cleanup
===========================

Use ``ct.first`` and ``ct.last`` for setup and teardown:

.. code-block:: python

    def main_cycle(ct: revpimodio2.Cycletools):
        if ct.first:
            # Initialize on first cycle
            ct.var.counter = 0
            ct.var.state = "IDLE"
            print("System started")

        # Main logic runs every cycle
        ct.var.counter += 1

        if ct.last:
            # Cleanup before exit
            ct.io.motor.value = False
            print(f"Total cycles: {ct.var.counter}")

    rpi = revpimodio2.RevPiModIO(autorefresh=True)
    rpi.cycleloop(main_cycle)

Persistent Variables
====================

Use ``ct.var`` to store variables that persist between cycles:

.. code-block:: python

    def main_cycle(ct):
        if ct.first:
            ct.var.counter = 0
            ct.var.state = "IDLE"
            ct.var.accumulator = 0.0

        # Variables persist between cycles
        ct.var.counter += 1
        ct.var.accumulator += ct.io.sensor.value

        # Access variables later
        average = ct.var.accumulator / ct.var.counter

Variables defined in ``ct.var`` maintain their values across all cycle executions.

Change Detection
================

Detect input changes efficiently without storing previous values:

.. code-block:: python

    def main_cycle(ct: revpimodio2.Cycletools):
        # Detect any change
        if ct.changed(ct.io.sensor):
            print(f"Sensor changed to: {ct.io.sensor.value}")

        # Detect rising edge (button press)
        if ct.changed(ct.io.button, edge=revpimodio2.RISING):
            print("Button pressed!")

        # Detect falling edge (button release)
        if ct.changed(ct.io.button, edge=revpimodio2.FALLING):
            print("Button released!")

    rpi = revpimodio2.RevPiModIO(autorefresh=True)
    rpi.cycleloop(main_cycle)

Edge types:

* ``revpimodio2.RISING`` - False to True transition
* ``revpimodio2.FALLING`` - True to False transition
* ``revpimodio2.BOTH`` - Any change (default)

Timing Flags
============

Built-in timing flags provide periodic execution without manual counting.

Toggle Flags
------------

Toggle flags alternate between True/False at regular intervals:

.. code-block:: python

    def main_cycle(ct):
        # Blink LED - flag5c alternates every 5 cycles
        ct.io.blink_led.value = ct.flag5c

        # Different blink rates
        ct.io.fast_blink.value = ct.flag2c    # Every 2 cycles
        ct.io.slow_blink.value = ct.flag20c   # Every 20 cycles

**Available toggle flags:**

* ``ct.flag1c`` - Every cycle
* ``ct.flag2c`` - Every 2 cycles
* ``ct.flag5c`` - Every 5 cycles
* ``ct.flag10c`` - Every 10 cycles
* ``ct.flag20c`` - Every 20 cycles

Flank Flags
-----------

Flank flags are True for exactly one cycle at regular intervals:

.. code-block:: python

    def main_cycle(ct):
        # Execute task every 10 cycles
        if ct.flank10c:
            print(f"Runtime: {ct.runtime:.3f}s")

        # Execute task every 20 cycles
        if ct.flank20c:
            temp = ct.io.temperature.value
            print(f"Temperature: {temp}°C")

**Available flank flags:**

* ``ct.flank5c`` - True every 5 cycles
* ``ct.flank10c`` - True every 10 cycles
* ``ct.flank15c`` - True every 15 cycles
* ``ct.flank20c`` - True every 20 cycles

Timers
======

RevPiModIO provides three timer types based on PLC standards. All timers are specified in cycle counts.

On-Delay Timer (TON/TONC)
--------------------------

Output becomes True only after input is continuously True for specified cycles:

.. code-block:: python

    def main_cycle(ct):
        # Input: sensor value
        ct.set_tonc("delay", 10)

        # Output goes high after input is high for 10 cycles
        if ct.get_tonc("delay"):
            ct.io.output.value = True
        else:
            ct.io.output.value = False

**How it works:**

1. Input goes True
2. Timer starts counting
3. If input stays True for 10 cycles, output goes True
4. If input goes False before 10 cycles, timer resets

**Use cases:**

* Button debouncing
* Startup delays
* Confirming sustained conditions

Off-Delay Timer (TOF/TOFC)
---------------------------

Output stays True for specified cycles after input goes False:

.. code-block:: python

    def main_cycle(ct):
        # Input: button value
        ct.set_tofc("motor_coast", 20)

        # Motor continues for 20 cycles after button release
        ct.io.motor.value = ct.get_tofc("motor_coast")

**How it works:**

1. Input is True, output is True
2. Input goes False
3. Output stays True for 20 more cycles
4. After 20 cycles, output goes False

**Use cases:**

* Motor coast-down
* Relay hold-in
* Graceful shutdowns

Pulse Timer (TP/TPC)
--------------------

Generates a one-shot pulse of specified duration:

.. code-block:: python

    def main_cycle(ct):
        # Trigger pulse on button press
        if ct.changed(ct.io.trigger, edge=revpimodio2.RISING):
            ct.set_tpc("pulse", 5)

        # Output is True for 5 cycles
        ct.io.pulse_output.value = ct.get_tpc("pulse")

**How it works:**

1. Call ``set_tpc`` to trigger pulse
2. Output is True for 5 cycles
3. After 5 cycles, output goes False
4. Additional triggers during pulse are ignored

**Use cases:**

* One-shot operations
* Acknowledgment pulses
* Retriggerable delays

Converting Time to Cycles
--------------------------

Calculate cycles from desired time:

.. code-block:: python

    # At 20ms cycle time:
    # 1 second = 50 cycles
    # 100ms = 5 cycles
    # 2 seconds = 100 cycles

    def main_cycle(ct):
        cycle_time_ms = rpi.cycletime
        desired_time_ms = 1500  # 1.5 seconds

        cycles_needed = int(desired_time_ms / cycle_time_ms)
        ct.set_tonc("my_delay", cycles_needed)

State Machines
==============

State machines implement complex control logic with distinct operational modes.

Simple State Machine
---------------------

.. code-block:: python

    def traffic_light(ct: revpimodio2.Cycletools):
        """Traffic light controller."""

        if ct.first:
            ct.var.state = "GREEN"

        if ct.var.state == "GREEN":
            ct.io.green_led.value = True
            ct.io.yellow_led.value = False
            ct.io.red_led.value = False

            # After 100 cycles (2s @ 20ms), go to yellow
            ct.set_tonc("green_time", 100)
            if ct.get_tonc("green_time"):
                ct.var.state = "YELLOW"

        elif ct.var.state == "YELLOW":
            ct.io.green_led.value = False
            ct.io.yellow_led.value = True

            ct.set_tonc("yellow_time", 25)  # 500ms
            if ct.get_tonc("yellow_time"):
                ct.var.state = "RED"

        elif ct.var.state == "RED":
            ct.io.yellow_led.value = False
            ct.io.red_led.value = True

            ct.set_tonc("red_time", 150)  # 3s
            if ct.get_tonc("red_time"):
                ct.var.state = "GREEN"

    rpi = revpimodio2.RevPiModIO(autorefresh=True)
    rpi.cycleloop(traffic_light)

Complex State Machine
----------------------

.. code-block:: python

    def machine_controller(ct: revpimodio2.Cycletools):
        """Multi-state machine controller."""

        if ct.first:
            ct.var.state = "IDLE"
            ct.var.production_count = 0

        # State: IDLE - Ready to start
        if ct.var.state == "IDLE":
            ct.io.motor.value = False
            ct.io.green_led.value = True
            ct.io.red_led.value = False

            if ct.changed(ct.io.start_button, edge=revpimodio2.RISING):
                ct.var.state = "STARTING"
                print("Starting...")

        # State: STARTING - Startup sequence
        elif ct.var.state == "STARTING":
            ct.io.yellow_led.value = True

            # 2-second startup delay
            ct.set_tonc("startup", 100)
            if ct.get_tonc("startup"):
                ct.var.state = "RUNNING"
                print("Running")

        # State: RUNNING - Normal operation
        elif ct.var.state == "RUNNING":
            ct.io.motor.value = True
            ct.io.yellow_led.value = False
            ct.io.green_led.value = ct.flag5c  # Blink

            # Count production
            if ct.changed(ct.io.sensor, edge=revpimodio2.RISING):
                ct.var.production_count += 1

            # Check for stop
            if ct.io.stop_button.value:
                ct.var.state = "STOPPING"

            # Check for error
            if ct.io.error_sensor.value:
                ct.var.state = "ERROR"

        # State: STOPPING - Controlled shutdown
        elif ct.var.state == "STOPPING":
            # Coast motor for 1 second
            ct.set_tofc("coast", 50)
            ct.io.motor.value = ct.get_tofc("coast")

            if not ct.io.motor.value:
                ct.var.state = "IDLE"
                print("Stopped")

        # State: ERROR - Fault condition
        elif ct.var.state == "ERROR":
            ct.io.motor.value = False
            ct.io.red_led.value = ct.flag2c  # Blink red

            if ct.changed(ct.io.ack_button, edge=revpimodio2.RISING):
                if not ct.io.error_sensor.value:
                    ct.var.state = "IDLE"
                    print("Error cleared")

        if ct.last:
            print(f"Total production: {ct.var.production_count}")

    rpi = revpimodio2.RevPiModIO(autorefresh=True)
    rpi.cycleloop(machine_controller)

Practical Examples
==================

Temperature Control
-------------------

Temperature monitoring with hysteresis control:

.. code-block:: python

    def temperature_monitor(ct: revpimodio2.Cycletools):
        """Monitor temperature and control cooling."""

        if ct.first:
            ct.var.cooling_active = False

        temp = ct.io.temperature.value

        # Hysteresis: ON at 75°C, OFF at 65°C
        if temp > 75 and not ct.var.cooling_active:
            ct.io.cooling_fan.value = True
            ct.var.cooling_active = True
            print(f"Cooling ON: {temp}°C")

        elif temp < 65 and ct.var.cooling_active:
            ct.io.cooling_fan.value = False
            ct.var.cooling_active = False
            print(f"Cooling OFF: {temp}°C")

        # Warning if too hot
        if temp > 85:
            ct.io.warning_led.value = ct.flag2c  # Blink

        # Emergency shutdown
        if temp > 95:
            ct.io.emergency_shutdown.value = True

    rpi = revpimodio2.RevPiModIO(autorefresh=True)
    rpi.cycleloop(temperature_monitor)

Production Counter
------------------

Count production items with start/stop control:

.. code-block:: python

    def production_counter(ct: revpimodio2.Cycletools):
        """Track production count."""

        if ct.first:
            ct.var.total_count = 0
            ct.var.running = False

        # Start/stop control
        if ct.changed(ct.io.start_button, edge=revpimodio2.RISING):
            ct.var.running = True

        if ct.changed(ct.io.stop_button, edge=revpimodio2.RISING):
            ct.var.running = False

        # Count items
        if ct.var.running:
            if ct.changed(ct.io.item_sensor, edge=revpimodio2.RISING):
                ct.var.total_count += 1
                ct.set_tpc("count_pulse", 5)  # Pulse LED
                print(f"Item #{ct.var.total_count}")

        ct.io.count_led.value = ct.get_tpc("count_pulse")

        # Reset counter
        if ct.changed(ct.io.reset_button, edge=revpimodio2.RISING):
            print(f"Final count: {ct.var.total_count}")
            ct.var.total_count = 0

    rpi = revpimodio2.RevPiModIO(autorefresh=True)
    rpi.cycleloop(production_counter)

Best Practices
==============

Keep Cycle Logic Fast
----------------------

Minimize processing time in each cycle:

.. code-block:: python

    def optimized_cycle(ct):
        # Heavy work only when needed
        if ct.flank100c:
            heavy_calculation()

        # Keep cycle logic minimal
        ct.io.output.value = ct.io.input.value

**Guidelines:**

* Avoid blocking operations (network, file I/O)
* Use flank flags for expensive operations
* Keep cycle time ≥20ms for stability

Use Appropriate Cycle Time
---------------------------

Match cycle time to application requirements:

.. code-block:: python

    # Fast control (motion, high-speed counting)
    rpi.cycletime = 20  # 50 Hz

    # Normal control (most applications)
    rpi.cycletime = 50  # 20 Hz

    # Slow monitoring (temperature, status)
    rpi.cycletime = 100  # 10 Hz

Handle Errors Safely
--------------------

Always implement safe failure modes:

.. code-block:: python

    def safe_cycle(ct):
        try:
            value = ct.io.sensor.value
            ct.io.output.value = process(value)
        except Exception as e:
            print(f"Error: {e}")
            ct.io.output.value = False  # Safe state

Initialize Properly
-------------------

Use ``ct.first`` for all initialization:

.. code-block:: python

    def main_cycle(ct):
        if ct.first:
            # Initialize all variables
            ct.var.counter = 0
            ct.var.state = "IDLE"
            ct.var.last_value = 0

            # Set initial outputs
            ct.io.motor.value = False

See Also
========

* :doc:`basics` - Core concepts and configuration
* :doc:`event_programming` - Event-driven programming
* :doc:`advanced` - Advanced topics and examples
* :doc:`api/helper` - Cycletools API reference
