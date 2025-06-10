# Agent guidelines

This repository contains a Django project managed with Poetry.

* Install dependencies using `poetry install`.
* Before running tests, apply migrations with
  `poetry run course-management/manage.py migrate --settings=course.settings_test --noinput`.
* Run the test suite using `poetry run pytest` and ensure it passes.

