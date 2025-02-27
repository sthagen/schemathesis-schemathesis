Experimental features
=====================

Introduction
------------

This section provides an overview of experimental features in Schemathesis - features that are under development and available for testing, but not yet considered stable.

This section provides an overview of experimental features in Schemathesis.
These are features that are under development, available for user testing but not yet stable.
Experimental features offer a glimpse into upcoming functionalities and enhancements, providing users an opportunity to try out and contribute feedback to shape their final form.

.. note::

   Experimental features can change or be removed in any minor version release.

Enabling Experimental Features
------------------------------

Schemathesis provides a few ways to enable experimental features: via the CLI, Python tests, and environment variables.

.. _experimental-cli:

In CLI
~~~~~~

To enable an experimental feature via the CLI, use the ``--experimental`` option.

For example, to enable experimental support for OpenAPI 3.1:

.. code-block:: bash

   st run https://example.schemathesis.io/openapi.json --experimental=openapi-3.1

.. _experimental-python:

In Python Tests
~~~~~~~~~~~~~~~

To enable experimental features for your Schemathesis tests in Python, use the ``enable`` method on the desired experimental feature. It's a good idea to put the code to enable the feature in a place that runs before your tests start. For those using ``pytest``, putting this code in a ``conftest.py`` file at the root of your test directory would work well.

.. code-block:: python

    import schemathesis

    # Globally enable OpenAPI 3.1 experimental feature
    schemathesis.experimental.OPEN_API_3_1.enable()

Executing the above code will ensure that Schemathesis will utilize the enabled experimental features in all tests run afterwards.

.. note::

    This action will apply globally, affecting all your tests. Use with caution.

Using Environment Variables
~~~~~~~~~~~~~~~~~~~~~~~~~~~

You can also enable experimental features through environment variables. This is particularly useful for CI/CD pipelines or when you don't have direct control over CLI arguments or test code.

For example, to enable experimental support for OpenAPI 3.1:

.. code-block:: bash

    export SCHEMATHESIS_EXPERIMENTAL_OPENAPI_3_1=true

This will enable the OpenAPI 3.1 experimental feature for any Schemathesis runs in the same environment.

Current Experimental Features
-----------------------------

Positive Data Acceptance
~~~~~~~~~~~~~~~~~~~~~~~~

Verifies that schema-conforming data receives 2xx status responses, highlighting mismatches between schema and API behavior across all endpoints.

**Allowed status codes**: 2xx, 401, 403, 404

**Note**: May produce false positives with complex validation that is not reflected in the schema.

.. _positive-data-acceptance-cli:

In CLI
~~~~~~

.. code-block:: bash

   st run https://example.schemathesis.io/openapi.json --experimental=positive-data-acceptance

Configuration options:

.. code-block:: bash

   --experimental-positive-data-acceptance-allowed-statuses=202

.. _positive-data-acceptance-env-vars:

Using Environment Variables
~~~~~~~~~~~~~~~~~~~~~~~~~~~

To enable Positive Data Acceptance via environment variables:

.. code-block:: bash

    export SCHEMATHESIS_EXPERIMENTAL_POSITIVE_DATA_ACCEPTANCE=true

Configure status codes:

.. code-block:: bash

    export SCHEMATHESIS_EXPERIMENTAL_POSITIVE_DATA_ACCEPTANCE_ALLOWED_STATUSES=201,202,204

For more details, join the `GitHub Discussion #2499 <https://github.com/schemathesis/schemathesis/discussions/2499>`_.

Negative Data Rejection
~~~~~~~~~~~~~~~~~~~~~~~

This feature covers configuring the ``negative_data_rejection`` check and allows for defining what status codes won't trigger this check.

**Allowed status codes**: 400, 401, 403, 404, 422, 5XX

In CLI
~~~~~~

Configuration options:

.. code-block:: bash

   --experimental-negative-data-rejection-allowed-statuses=4XX

Using Environment Variables
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Configure status codes:

.. code-block:: bash

    export SCHEMATHESIS_EXPERIMENTAL_NEGATIVE_DATA_REJECTION_ALLOWED_STATUSES=4XX

Stabilization of Experimental Features
--------------------------------------

Criteria for moving a feature from experimental to stable status include:

- Full coverage of planned functionality
- API design stability, assessed through user feedback and internal review

Providing Feedback
------------------

Feedback is crucial for the development and stabilization of experimental features. We encourage you to share your thoughts via `GitHub Discussions <https://github.com/schemathesis/schemathesis/discussions>`_

.. note::

   When you use an experimental feature, a notice will appear in your test output, providing a link to the corresponding GitHub discussion where you can leave feedback.
