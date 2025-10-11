.. restmachine documentation master file

Welcome to restmachine's documentation!
========================================

restmachine is a lightweight REST framework with pytest-like dependency injection,
webmachine-style state machine, content negotiation support, and Pydantic-based validation.

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   api

Quick Start
-----------

The restmachine framework provides a Flask-like interface with powerful dependency injection
capabilities, a webmachine-inspired state machine, flexible content negotiation,
and comprehensive request/response validation using Pydantic models.

Basic Example
~~~~~~~~~~~~~

.. code-block:: python

   from restmachine import RestApplication

   app = RestApplication()

   @app.route('/hello')
   def hello():
       return {'message': 'Hello, World!'}

Features
--------

* **Dependency Injection**: pytest-like dependency injection system
* **State Machine**: webmachine-inspired state machine for REST resource handling
* **Content Negotiation**: Flexible content negotiation with multiple renderers
* **Validation**: Pydantic-based request/response validation
* **Lightweight**: Minimal dependencies and simple API

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`