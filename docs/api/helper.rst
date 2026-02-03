==============
Helper Classes
==============

Helper classes for cyclic and event-driven programming.

.. currentmodule:: revpimodio2.helper

Cycletools
==========

.. autoclass:: Cycletools
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__

   Toolkit provided to cyclic functions via ``.cycleloop()``.

   This class provides tools for cyclic functions including timing flags
   and edge markers. Note that edge markers (flank flags) are all True
   during the first cycle!

   **Attributes:**



      Reference to RevPiModIO core object



      Reference to RevPiModIO device object



      Reference to RevPiModIO io object



      True only on first cycle



      True when shutdown signal received



      Current function execution time in seconds



      Container for cycle-persistent variables

   **Toggle Flags** - Alternate between True/False:



      1 cycle True, 1 cycle False



      2 cycles True, 2 cycles False



      5 cycles True, 5 cycles False



      10 cycles True, 10 cycles False



      20 cycles True, 20 cycles False

   **Flank Flags** - True every nth cycle:



      True every 5 cycles



      True every 10 cycles



      True every 15 cycles



      True every 20 cycles

   **Example:**

   .. code-block:: python

       def main(ct: revpimodio2.Cycletools):
           if ct.first:
               # Initialize
               ct.var.counter = 0

           # Main logic
           if ct.changed(ct.io.sensor):
               ct.var.counter += 1

           # Blink LED using timing flag
           ct.io.led.value = ct.flag5c

           if ct.last:
               # Cleanup
               print(f"Final: {ct.var.counter}")

Change Detection
----------------


Timer Functions
---------------

On-Delay Timers
~~~~~~~~~~~~~~~


Off-Delay Timers
~~~~~~~~~~~~~~~~


Pulse Timers
~~~~~~~~~~~~


EventCallback
=============

.. autoclass:: EventCallback
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__

   Thread for internal event function calls.

   This class is passed to threaded event handlers registered with
   ``as_thread=True``. The event function receives this thread object
   as a parameter to access event information and control execution.

   **Attributes:**



      Name of IO that triggered the event



      Value of IO when event was triggered



      Threading event for abort conditions

   **Example:**

   .. code-block:: python

       def threaded_handler(eventcallback: revpimodio2.EventCallback):
           print(f"{eventcallback.ioname} = {eventcallback.iovalue}")

           # Interruptible wait (3 seconds)
           if eventcallback.exit.wait(3):
               print("Wait interrupted!")
               return

           # Check if stop was called
           if eventcallback.exit.is_set():
               return

       # Register as threaded event
       rpi.io.button.reg_event(threaded_handler, as_thread=True)

Methods
-------


ProcimgWriter
=============

.. autoclass:: ProcimgWriter
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__

   Internal thread for process image writing and event management.
