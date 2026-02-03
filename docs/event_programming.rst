====================
Event Programming
====================

Event-driven programming uses callbacks triggered by hardware state changes.

.. contents:: Contents
   :local:
   :depth: 2

When to Use Event-Driven Programming
=====================================

**Event-driven programming is ideal for:**

* Handling user interactions
* Processing occasional events
* Background tasks
* System integration
* Low CPU usage requirements

**Advantages:**

* Consumes CPU only when events occur
* Natural for user interfaces
* Simple asynchronous operation
* Efficient for sporadic events

**Considerations:**

* Non-deterministic timing
* Must handle concurrent events carefully
* Less intuitive for continuous control

Basic Structure
===============

Simple Event Handler
--------------------

.. code-block:: python

    import revpimodio2

    rpi = revpimodio2.RevPiModIO(autorefresh=True)

    def on_button_change(ioname, iovalue):
        """Called when button changes."""
        print(f"{ioname} = {iovalue}")
        rpi.io.led.value = iovalue

    # Register event
    rpi.io.button.reg_event(on_button_change)

    # Run main loop
    rpi.handlesignalend()
    rpi.mainloop()

The callback function receives:

* ``ioname`` - Name of the IO that changed
* ``iovalue`` - New value of the IO

Event Registration
==================

Value Change Events
-------------------

Register callbacks for IO value changes:

.. code-block:: python

    def on_change(ioname, iovalue):
        print(f"{ioname} changed to {iovalue}")

    rpi = revpimodio2.RevPiModIO(autorefresh=True)

    # Any change
    rpi.io.sensor.reg_event(on_change)

    # Rising edge only
    rpi.io.button.reg_event(on_change, edge=revpimodio2.RISING)

    # Falling edge only
    rpi.io.button.reg_event(on_change, edge=revpimodio2.FALLING)

    rpi.handlesignalend()
    rpi.mainloop()

**Edge types:**

* ``revpimodio2.RISING`` - False to True transition
* ``revpimodio2.FALLING`` - True to False transition
* ``revpimodio2.BOTH`` - Any change (default)

Lambda Functions
----------------

Use lambda for simple callbacks:

.. code-block:: python

    rpi = revpimodio2.RevPiModIO(autorefresh=True)

    # Simple lambda callback
    rpi.io.button.reg_event(
        lambda name, val: print(f"Button: {val}")
    )

    # Lambda with edge filter
    rpi.io.start_button.reg_event(
        lambda name, val: print("Started!"),
        edge=revpimodio2.RISING
    )

    rpi.handlesignalend()
    rpi.mainloop()

Multiple Events
---------------

Register multiple callbacks on one IO:

.. code-block:: python

    def on_press(ioname, iovalue):
        print("Pressed!")

    def on_release(ioname, iovalue):
        print("Released!")

    rpi = revpimodio2.RevPiModIO(autorefresh=True)

    # Different callbacks for different edges
    rpi.io.button.reg_event(on_press, edge=revpimodio2.RISING)
    rpi.io.button.reg_event(on_release, edge=revpimodio2.FALLING)

    rpi.handlesignalend()
    rpi.mainloop()

Or register one callback on multiple IOs:

.. code-block:: python

    def any_sensor_changed(ioname, iovalue):
        print(f"{ioname} changed to {iovalue}")

    rpi = revpimodio2.RevPiModIO(autorefresh=True)

    # Same callback for multiple sensors
    for sensor in ["sensor1", "sensor2", "sensor3"]:
        if sensor in rpi.io:
            rpi.io[sensor].reg_event(any_sensor_changed)

    rpi.handlesignalend()
    rpi.mainloop()

Debouncing
==========

Add debounce delays to filter noise and false triggers:

.. code-block:: python

    def on_stable_press(ioname, iovalue):
        """Called only after button is stable for 50ms."""
        print(f"Confirmed: {iovalue}")

    rpi = revpimodio2.RevPiModIO(autorefresh=True)

    # 50ms debounce delay
    rpi.io.noisy_button.reg_event(on_stable_press, delay=50)

    rpi.handlesignalend()
    rpi.mainloop()

**How debouncing works:**

1. IO value changes
2. RevPiModIO waits for ``delay`` milliseconds
3. If value is still changed, callback is triggered
4. If value changed back, callback is not triggered

**Typical debounce times:**

* Mechanical switches: 20-50ms
* Relays: 10-20ms
* Analog sensors: 100-500ms

Debouncing with Edge Detection
-------------------------------

.. code-block:: python

    def on_confirmed_press(ioname, iovalue):
        """Called only for stable button press."""
        print("Confirmed press")

    rpi = revpimodio2.RevPiModIO(autorefresh=True)

    # Rising edge with 30ms debounce
    rpi.io.button.reg_event(
        on_confirmed_press,
        edge=revpimodio2.RISING,
        delay=30
    )

    rpi.handlesignalend()
    rpi.mainloop()

Timer Events
============

Execute callbacks at regular intervals independent of IO changes:

.. code-block:: python

    def periodic_task(ioname, iovalue):
        """Called every 500ms."""
        print(f"Periodic task: {iovalue}")

    rpi = revpimodio2.RevPiModIO(autorefresh=True)

    # Execute every 500ms
    rpi.io.dummy.reg_timerevent(periodic_task, 500)

    rpi.handlesignalend()
    rpi.mainloop()

Timer Event Parameters
----------------------

.. code-block:: python

    rpi = revpimodio2.RevPiModIO(autorefresh=True)

    def blink_led(ioname, iovalue):
        """Toggle LED every 500ms."""
        rpi.io.blink_led.value = not rpi.io.blink_led.value

    def log_temperature(ioname, iovalue):
        """Log temperature every 5 seconds."""
        temp = rpi.io.temperature.value
        print(f"Temperature: {temp}°C")

    # Blink every 500ms, trigger immediately
    rpi.io.blink_led.reg_timerevent(blink_led, 500, prefire=True)

    # Log every 5 seconds, don't trigger immediately
    rpi.io.temperature.reg_timerevent(log_temperature, 5000, prefire=False)

    rpi.handlesignalend()
    rpi.mainloop()

**Parameters:**

* ``interval`` - Milliseconds between calls
* ``prefire`` - If True, trigger immediately on registration

Threaded Events
===============

Use threaded events for long-running operations that would block the main loop:

.. code-block:: python

    def long_task(eventcallback: revpimodio2.EventCallback):
        """Threaded handler for time-consuming tasks."""
        print(f"Starting task for {eventcallback.ioname}")

        for i in range(10):
            # Check if stop requested
            if eventcallback.exit.is_set():
                print("Task cancelled")
                return

            # Interruptible wait (1 second)
            eventcallback.exit.wait(1)
            print(f"Progress: {(i+1)*10}%")

        print("Task complete")

    rpi = revpimodio2.RevPiModIO(autorefresh=True)

    # Register as threaded event
    rpi.io.trigger.reg_event(
        long_task,
        as_thread=True,
        edge=revpimodio2.RISING
    )

    rpi.handlesignalend()
    rpi.mainloop()

EventCallback Object
--------------------

Threaded callbacks receive an ``EventCallback`` object with:

* ``eventcallback.ioname`` - Name of the IO
* ``eventcallback.iovalue`` - Value that triggered event
* ``eventcallback.exit`` - ``threading.Event`` for cancellation

**Important:** Always check ``eventcallback.exit.is_set()`` periodically to allow graceful shutdown.

Interruptible Sleep
-------------------

Use ``eventcallback.exit.wait()`` instead of ``time.sleep()`` for interruptible delays:

.. code-block:: python

    def background_task(eventcallback: revpimodio2.EventCallback):
        """Long task with interruptible waits."""

        while not eventcallback.exit.is_set():
            # Do some work
            process_data()

            # Wait 5 seconds or until exit requested
            if eventcallback.exit.wait(5):
                break  # Exit was requested

    rpi = revpimodio2.RevPiModIO(autorefresh=True)
    rpi.io.trigger.reg_event(background_task, as_thread=True)
    rpi.handlesignalend()
    rpi.mainloop()

Unregistering Events
====================

Remove event callbacks when no longer needed:

.. code-block:: python

    def my_callback(ioname, iovalue):
        print(f"{ioname} = {iovalue}")

    rpi = revpimodio2.RevPiModIO(autorefresh=True)

    # Register event
    rpi.io.button.reg_event(my_callback)

    # Unregister specific callback
    rpi.io.button.unreg_event(my_callback)

    # Unregister all events for this IO
    rpi.io.button.unreg_event()

Practical Examples
==================

LED Toggle on Button Press
---------------------------

.. code-block:: python

    import revpimodio2

    rpi = revpimodio2.RevPiModIO(autorefresh=True)

    def toggle_led(ioname, iovalue):
        """Toggle LED on button press."""
        rpi.io.led.value = not rpi.io.led.value
        print(f"LED: {rpi.io.led.value}")

    rpi.io.button.reg_event(toggle_led, edge=revpimodio2.RISING)
    rpi.handlesignalend()
    rpi.mainloop()

Multiple Button Handler
------------------------

.. code-block:: python

    import revpimodio2

    rpi = revpimodio2.RevPiModIO(autorefresh=True)

    def on_start(ioname, iovalue):
        print("Starting motor...")
        rpi.io.motor.value = True
        rpi.core.A1 = revpimodio2.GREEN

    def on_stop(ioname, iovalue):
        print("Stopping motor...")
        rpi.io.motor.value = False
        rpi.core.A1 = revpimodio2.RED

    def on_emergency(ioname, iovalue):
        print("EMERGENCY STOP!")
        rpi.io.motor.value = False
        rpi.io.alarm.value = True
        rpi.core.A1 = revpimodio2.RED

    # Register different buttons
    rpi.io.start_button.reg_event(on_start, edge=revpimodio2.RISING)
    rpi.io.stop_button.reg_event(on_stop, edge=revpimodio2.RISING)
    rpi.io.emergency_stop.reg_event(on_emergency, edge=revpimodio2.RISING)

    rpi.handlesignalend()
    rpi.mainloop()

Sensor Logging
--------------

.. code-block:: python

    import revpimodio2
    from datetime import datetime

    rpi = revpimodio2.RevPiModIO(autorefresh=True)

    def log_sensor_change(ioname, iovalue):
        """Log sensor changes with timestamp."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"{timestamp} - {ioname}: {iovalue}")

    # Log all sensor changes
    for io_name in ["sensor1", "sensor2", "temperature"]:
        if io_name in rpi.io:
            rpi.io[io_name].reg_event(log_sensor_change)

    rpi.handlesignalend()
    rpi.mainloop()

Periodic Status Report
----------------------

.. code-block:: python

    import revpimodio2

    rpi = revpimodio2.RevPiModIO(autorefresh=True)

    def status_report(ioname, iovalue):
        """Print system status every 10 seconds."""
        print("=== Status Report ===")
        print(f"Temperature: {rpi.core.temperature.value}°C")
        print(f"CPU Frequency: {rpi.core.frequency.value} MHz")
        print(f"IO Errors: {rpi.core.ioerrorcount.value}")
        print()

    # Status report every 10 seconds
    rpi.io.dummy.reg_timerevent(status_report, 10000, prefire=True)

    rpi.handlesignalend()
    rpi.mainloop()

Threaded Data Processing
-------------------------

.. code-block:: python

    import revpimodio2

    rpi = revpimodio2.RevPiModIO(autorefresh=True)

    def process_batch(eventcallback: revpimodio2.EventCallback):
        """Process data batch in background thread."""
        print(f"Starting batch processing...")

        batch_size = 100
        for i in range(batch_size):
            if eventcallback.exit.is_set():
                print("Processing cancelled")
                return

            # Simulate processing
            eventcallback.exit.wait(0.1)

            if i % 10 == 0:
                print(f"Progress: {i}/{batch_size}")

        print("Batch processing complete")
        rpi.io.done_led.value = True

    # Trigger on button press
    rpi.io.start_batch.reg_event(
        process_batch,
        as_thread=True,
        edge=revpimodio2.RISING
    )

    rpi.handlesignalend()
    rpi.mainloop()

Best Practices
==============

Keep Callbacks Fast
-------------------

Event callbacks should complete quickly:

.. code-block:: python

    # Good - Fast callback
    def good_callback(ioname, iovalue):
        rpi.io.output.value = iovalue

    # Poor - Blocking callback
    def poor_callback(ioname, iovalue):
        time.sleep(5)  # Blocks event loop!
        rpi.io.output.value = iovalue

For slow operations, use threaded events:

.. code-block:: python

    def slow_task(eventcallback):
        # Long operation in separate thread
        process_data()

    rpi.io.trigger.reg_event(slow_task, as_thread=True)

Use Debouncing
--------------

Always debounce mechanical inputs:

.. code-block:: python

    # Good - Debounced button
    rpi.io.button.reg_event(callback, delay=30)

    # Poor - No debounce (may trigger multiple times)
    rpi.io.button.reg_event(callback)

Handle Errors Gracefully
-------------------------

Protect callbacks from exceptions:

.. code-block:: python

    def safe_callback(ioname, iovalue):
        try:
            result = risky_operation(iovalue)
            rpi.io.output.value = result
        except Exception as e:
            print(f"Error in callback: {e}")
            rpi.io.output.value = False  # Safe state

Check IO Existence
------------------

Verify IOs exist before registering events:

.. code-block:: python

    if "optional_button" in rpi.io:
        rpi.io.optional_button.reg_event(callback)
    else:
        print("Optional button not configured")

Clean Up Threads
----------------

Threaded events are automatically cleaned up on exit, but you can manually unregister:

.. code-block:: python

    def long_task(eventcallback):
        while not eventcallback.exit.is_set():
            work()
            eventcallback.exit.wait(1)

    rpi = revpimodio2.RevPiModIO(autorefresh=True)

    # Register
    rpi.io.trigger.reg_event(long_task, as_thread=True)

    # Later: unregister to stop thread
    rpi.io.trigger.unreg_event(long_task)

See Also
========

* :doc:`basics` - Core concepts and configuration
* :doc:`cyclic_programming` - Cyclic programming patterns
* :doc:`advanced` - Combining paradigms and advanced topics
* :doc:`api/helper` - EventCallback API reference
