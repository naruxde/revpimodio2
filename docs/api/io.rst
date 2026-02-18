====================
IO Classes and Types
====================

Classes for managing Revolution Pi inputs and outputs.

.. currentmodule:: revpimodio2.io

IOList
======

.. autoclass:: IOList
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__, __getitem__, __contains__, __iter__

   Container for accessing all IO objects.

   The IOList provides multiple ways to access IOs:

   * **Direct attribute access**: ``rpi.io.button.value``
   * **String-based access**: ``rpi.io["button"].value``
   * **Iteration**: ``for io in rpi.io: ...``

   **Example:**

   .. code-block:: python

       # Direct access
       value = rpi.io.I_1.value
       rpi.io.O_1.value = True

       # String-based access
       value = rpi.io["I_1"].value

       # Check if IO exists
       if "sensor" in rpi.io:
           print(rpi.io.sensor.value)

       # Iterate all IOs
       for io in rpi.io:
           print(f"{io.name}: {io.value}")

IOBase
======

.. autoclass:: IOBase
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__

   Base class for all IO objects.

   **Properties:**



      IO name from piCtory configuration



      Current IO value (read/write)



      Byte address in process image



      Byte length (0 for single bits)



      IO type: 300=INPUT, 301=OUTPUT, 302=MEMORY



      Whether value is signed



      "little" or "big" endian



      Configured default value from piCtory



      Comment/description from piCtory



      Export flag status

Event Registration Methods
---------------------------


Value Manipulation Methods
---------------------------


IntIO
=====

.. autoclass:: IntIO
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__

   IO objects with integer value access.

   **Example:**

   .. code-block:: python

       # Get integer value
       temp = rpi.io.temperature.get_intvalue()

       # Set integer value
       rpi.io.setpoint.set_intvalue(1500)

Integer Value Methods
---------------------


IntIOCounter
============

.. autoclass:: IntIOCounter
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__

   Counter input objects with reset capability.

   **Example:**

   .. code-block:: python

       # Read counter
       count = rpi.io.counter.value

       # Reset counter
       rpi.io.counter.reset()

StructIO
========

.. autoclass:: StructIO
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__

   Structured IO with format strings for complex data types.

   **Example:**

   .. code-block:: python

       # Get structured value
       value = rpi.io.sensor_data.get_structvalue()

Structured Value Methods
------------------------


MemIO
=====

.. autoclass:: MemIO
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__

   Memory IO with variant value access (string or integer).

RelaisOutput
============

.. autoclass:: RelaisOutput
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__

   Relay output with switching cycle counter.

   **Example:**

   .. code-block:: python

       # Get number of switching cycles
       cycles = rpi.io.relay.get_switching_cycles()

IOEvent
=======

.. autoclass:: IOEvent
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__

   Internal class for IO event management.
