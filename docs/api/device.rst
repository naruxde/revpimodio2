==============
Device Classes
==============

Classes for managing Revolution Pi devices.

.. currentmodule:: revpimodio2.device

Device
======

.. autoclass:: Device
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__

   Base class for all Revolution Pi devices.

DeviceList
==========

.. autoclass:: DeviceList
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__, __getitem__, __iter__

   Container for accessing devices.

   **Example:**

   .. code-block:: python

       # Access device by name
       dio_module = rpi.device.DIO_Module_1

       # Access device by position
       first_device = rpi.device[0]

       # Iterate all devices
       for device in rpi.device:
           print(f"Device: {device.name}")

Base
====

.. autoclass:: Base
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__

   Base class for Revolution Pi base modules.

GatewayMixin
============

.. autoclass:: GatewayMixin
   :members:
   :undoc-members:
   :show-inheritance:

   Mixin class providing gateway functionality for piGate modules.

ModularBaseConnect_4_5
======================

.. autoclass:: ModularBaseConnect_4_5
   :members:
   :undoc-members:
   :show-inheritance:
   :inherited-members:
   :special-members: __init__

   Base class for Connect 4 and Connect 5 modules.

Core
====

.. autoclass:: Core
   :members:
   :undoc-members:
   :show-inheritance:
   :inherited-members:
   :special-members: __init__

   Revolution Pi Core module.

Connect
=======

.. autoclass:: Connect
   :members:
   :undoc-members:
   :show-inheritance:
   :inherited-members:
   :special-members: __init__

   Revolution Pi Connect module.

Connect4
========

.. autoclass:: Connect4
   :members:
   :undoc-members:
   :show-inheritance:
   :inherited-members:
   :special-members: __init__

   Revolution Pi Connect 4 module.

Connect5
========

.. autoclass:: Connect5
   :members:
   :undoc-members:
   :show-inheritance:
   :inherited-members:
   :special-members: __init__

   Revolution Pi Connect 5 module.

DioModule
=========

.. autoclass:: DioModule
   :members:
   :undoc-members:
   :show-inheritance:
   :inherited-members:
   :special-members: __init__

   Digital I/O module.

RoModule
========

.. autoclass:: RoModule
   :members:
   :undoc-members:
   :show-inheritance:
   :inherited-members:
   :special-members: __init__

   Relay output module.

Gateway
=======

.. autoclass:: Gateway
   :members:
   :undoc-members:
   :show-inheritance:
   :inherited-members:
   :special-members: __init__

   Gateway module (ModbusTCP, Profinet, etc.).

Virtual
=======

.. autoclass:: Virtual
   :members:
   :undoc-members:
   :show-inheritance:
   :inherited-members:
   :special-members: __init__

   Virtual device for custom applications.
